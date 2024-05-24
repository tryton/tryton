# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict
from itertools import groupby
from operator import attrgetter

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def is_done(self):
        done = super(Sale, self).is_done()
        if done:
            if any(l.supply_state == 'requested'
                    for l in self.lines if l.supply_on_sale):
                return False
        return done

    @classmethod
    def _process_shipment(cls, sales):
        pool = Pool()
        Product = pool.get('product.product')

        product_quantities = defaultdict(float)
        for (company, warehouse), sub_sales in groupby(
                filter(attrgetter('warehouse'), sales),
                key=attrgetter('company', 'warehouse')):
            sub_sales = list(sub_sales)
            products = {
                l.product for s in sub_sales for l in s.lines
                if l.product and l.product.supply_on_sale == 'stock_first'}
            locations = [warehouse.id]
            with Transaction().set_context(
                    company=company.id, locations=locations,
                    stock_assign=True,
                    stock_date_end=None):
                product_quantities.update(
                    (p, p.forecast_quantity)
                    for p in Product.browse(products))

            # purchase requests must be created before shipments to get
            # information about requests during the shipments creation like the
            # supplier
            cls._process_supply(sub_sales, product_quantities)
            product_quantities.clear()
        super()._process_shipment(sales)

    @classmethod
    def _process_supply(cls, sales, product_quantities):
        pool = Pool()
        Line = pool.get('sale.line')
        PurchaseRequest = pool.get('purchase.request')

        requests, lines = [], []
        for sale in sales:
            reqs, lns = sale.create_purchase_requests(product_quantities)
            requests.extend(reqs)
            lines.extend(lns)
        PurchaseRequest.save(requests)
        Line.save(lines)

        cls._update_moves_from_supply(sales)

    def create_purchase_requests(self, product_quantities):
        requests, lines = [], []
        for line in self.lines:
            request = line.get_purchase_request(product_quantities)
            if not request:
                continue
            requests.append(request)
            assert not line.purchase_request
            line.purchase_request = request
            lines.append(line)
        return requests, lines

    @classmethod
    def _update_moves_from_supply(cls, sales):
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')
        Move = pool.get('stock.move')

        shipments = set()

        def add_shipment(shipment):
            if (isinstance(shipment, Shipment)
                    and shipment.state in {'draft', 'waiting'}):
                shipments.add(shipment)

        moves_to_draft, moves_to_cancel = [], []
        for sale in sales:
            for line in sale.lines:
                for move in line.moves:
                    if move.state == 'staging':
                        if (not line.has_supply
                                or line.supply_state == 'supplied'):
                            moves_to_draft.append(move)
                        elif line.supply_state == 'cancelled':
                            moves_to_cancel.append(move)
                        else:
                            continue
                        add_shipment(move.shipment)
        if moves_to_draft:
            Move.draft(moves_to_draft)
        shipments = Shipment.browse(shipments)
        shipments_waiting = [s for s in shipments if s.state == 'waiting']
        if shipments:
            Shipment.draft(shipments)  # clear inventory moves
        if moves_to_cancel:
            Move.cancel(moves_to_cancel)
        if shipments:
            Shipment.wait([
                    s for s in shipments_waiting
                    if any(m.state != 'cancelled' for m in s.moves)])
            Shipment.cancel([
                    s for s in shipments
                    if all(m.state == 'cancelled' for m in s.moves)])


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    purchase_request = fields.Many2One('purchase.request', 'Purchase Request',
        ondelete='SET NULL', readonly=True)
    supply_state = fields.Function(fields.Selection([
                ('', ""),
                ('requested', "Requested"),
                ('supplied', "Supplied"),
                ('cancelled', "Cancelled"),
                ], "Supply State",
            states={
                'invisible': ~Eval('supply_state'),
                }), 'get_supply_state')

    @property
    def has_supply(self):
        return bool(self.purchase_request)

    def get_supply_state(self, name):
        if self.purchase_request is not None:
            if self.purchase_request.state == 'cancelled':
                return 'cancelled'
            else:
                purchase_line = self.purchase_request.purchase_line
                if purchase_line is not None:
                    purchase = purchase_line.purchase
                    if purchase.state in {'processing', 'done'}:
                        return 'supplied'
            return 'requested'
        return ''

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('purchase_request', None)
        return super().copy(lines, default=default)

    @property
    def supply_on_sale(self):
        "Returns True if the sale line has to be supply by purchase request"
        if (self.type != 'line'
                or self.sale.shipment_method == 'manual'
                or not self.product
                or self.quantity <= 0
                or any(m.state not in ['staging', 'cancelled']
                    for m in self.moves)):
            return False
        return bool(self.product.supply_on_sale)

    @property
    def ready_for_supply(self):
        if self.sale.shipment_method == 'invoice':
            # Ensure to create the request for the maximum paid
            invoice_skips = (
                set(self.sale.invoices_ignored)
                | set(self.sale.invoices_recreated))
            invoice_lines = [
                l for l in self.invoice_lines
                if l.invoice not in invoice_skips]
            if (not invoice_lines
                    or any(
                        (not l.invoice) or l.invoice.state != 'paid'
                        for l in invoice_lines)):
                return False
        return True

    def get_move(self, shipment_type):
        move = super().get_move(shipment_type)
        if (move
                and shipment_type == 'out'
                and self.has_supply):
            if self.supply_state == 'requested':
                move.state = 'staging'
        return move

    def _get_move_quantity(self, shipment_type):
        quantity = super()._get_move_quantity(shipment_type)
        if self.supply_on_sale and not self.ready_for_supply:
            quantity = 0
        return quantity

    def _get_purchase_request_product_supplier_pattern(self):
        return {
            'company': self.sale.company.id,
            }

    def get_purchase_request(self, product_quantities):
        """Return purchase request for the sale line
        depending on the product quantities"""
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        if (not self.supply_on_sale
                or self.purchase_request
                or not self.ready_for_supply
                or not self.product.purchasable):
            return

        product = self.product
        quantity = self._get_move_quantity('out')
        if product.supply_on_sale == 'stock_first':
            available_qty = product_quantities[product]
            available_qty = Uom.compute_qty(
                product.default_uom, available_qty, self.unit,
                round=False)
            if available_qty > 0:
                product_quantities[product] -= Uom.compute_qty(
                    self.unit, quantity, product.default_uom, round=False)
                return

        supplier, purchase_date = Request.find_best_supplier(product,
            self.shipping_date,
            **self._get_purchase_request_product_supplier_pattern())
        unit = product.purchase_uom or product.default_uom
        quantity = Uom.compute_qty(self.unit, quantity, unit)
        return Request(
            product=product,
            party=supplier,
            quantity=quantity,
            unit=unit,
            computed_quantity=quantity,
            computed_unit=unit,
            purchase_date=purchase_date,
            supply_date=self.shipping_date,
            company=self.sale.company,
            warehouse=self.warehouse,
            origin=self.sale,
            )

    def assign_supplied(self, quantities, grouping=('product',)):
        '''
        Assign supplied move
        The quantities will be updated according to assigned quantities.
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        ShipmentOut = pool.get('stock.shipment.out')

        if self.supply_state != 'supplied':
            return

        moves = set()
        for move in self.moves:
            shipment = move.shipment
            if isinstance(shipment, ShipmentOut):
                if shipment.warehouse_storage == shipment.warehouse_output:
                    inventory_moves = shipment.outgoing_moves
                else:
                    inventory_moves = shipment.inventory_moves
                for inv_move in inventory_moves:
                    if inv_move.product == self.product:
                        moves.add(inv_move)

        Move.assign_try(list(moves), grouping=grouping, pblc={
                self.company.id: quantities,
                })
