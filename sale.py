#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Sale', 'SaleLine']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    def create_shipment(self, shipment_type):
        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out':
            self.create_purchase_requests()
        return shipments

    def create_purchase_requests(self):
        'Create the purchase requests for the sale'
        for line in self.lines:
            request = line.get_purchase_request()
            if not request:
                continue
            request.save()
            assert not line.purchase_request
            line.purchase_request = request
            line.save()


class SaleLine:
    __name__ = 'sale.line'

    purchase_request = fields.Many2One('purchase.request', 'Purchase Request',
        ondelete='SET NULL', readonly=True)
    purchase_request_state = fields.Function(fields.Selection([
                ('', ''),
                ('requested', 'Requested'),
                ('purchased', 'Purchased'),
                ('cancel', 'Cancel'),
                ], 'Purchase Request State',
            states={
                'invisible': ~Eval('purchase_request_state'),
                }), 'get_purchase_request_state')

    @classmethod
    def get_purchase_request_state(cls, lines, name):
        states = dict((l.id, '') for l in lines)
        with Transaction().set_user(0, set_context=True):
            for line in cls.browse(states.keys()):
                if line.purchase_request is not None:
                    states[line.id] = 'requested'
                    purchase_line = line.purchase_request.purchase_line
                    if purchase_line is not None:
                        purchase = purchase_line.purchase
                        if purchase.state == 'cancel':
                            states[line.id] = 'cancel'
                        elif purchase.state in ('confirmed', 'done'):
                            states[line.id] = 'purchased'
        return states

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['purchase_request'] = None
        return super(SaleLine, cls).copy(lines, default=default)

    @property
    def supply_on_sale(self):
        "Returns True if the sale line has to be supply by purchase request"
        if (self.type != 'line'
                or not self.product
                or self.quantity <= 0
                or not self.product.purchasable):
            return False
        return self.product.supply_on_sale

    def get_move(self, shipment_type):
        move = super(SaleLine, self).get_move(shipment_type)
        if (shipment_type == 'out'
                and self.supply_on_sale):
            if self.purchase_request_state in ('', 'requested'):
                return
        return move

    def get_purchase_request(self):
        'Return purchase request for the sale line'
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        if not self.supply_on_sale or self.purchase_request:
            return

        product = self.product
        supplier, purchase_date = Request.find_best_supplier(product,
            self.delivery_date)
        uom = product.purchase_uom or product.default_uom
        quantity = Uom.compute_qty(self.unit, self.quantity, uom)
        with Transaction().set_user(0, set_context=True):
            return Request(
                product=product,
                party=supplier,
                quantity=quantity,
                uom=uom,
                computed_quantity=quantity,
                computed_uom=uom,
                purchase_date=purchase_date,
                supply_date=self.delivery_date,
                company=self.sale.company,
                warehouse=self.sale.warehouse,
                origin=self.sale,
                )

    def assign_supplied(self, location_quantities):
        '''
        Assign supplied move

        location_quantities will be updated according to assigned
        quantities.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')

        if self.purchase_request_state != 'purchased':
            return
        moves = set()
        for move in self.moves:
            for inv_move in move.shipment.inventory_moves:
                if inv_move.product.id == self.product.id:
                    moves.add(inv_move)
        for move in moves:
            if move.state != 'draft':
                continue
            location_qties_converted = {}
            for location_id, quantity in (
                    location_quantities.iteritems()):
                location_qties_converted[location_id] = (
                    Uom.compute_qty(move.product.default_uom,
                        quantity, move.uom, round=False))
            to_pick = move.pick_product(location_qties_converted)

            picked_qties = sum(qty for _, qty in to_pick)
            if picked_qties < move.quantity:
                first = False
                Move.write([move], {
                        'quantity': move.quantity - picked_qties,
                        })
            else:
                first = True
            for from_location, qty in to_pick:
                values = {
                    'from_location': from_location.id,
                    'quantity': qty,
                    }
                if first:
                    Move.write([move], values)
                    Move.assign([move])
                else:
                    Move.assign(Move.copy([move], default=values))

                qty_default_uom = Uom.compute_qty(move.uom, qty,
                    move.product.default_uom, round=False)

                location_quantities[from_location] -= qty_default_uom
