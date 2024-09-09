# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, Workflow, fields
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if isinstance(move.origin, PurchaseLineComponent):
                    move.origin.check_move_quantity()
        super().receive(shipments)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if isinstance(move.origin, SaleLineComponent):
                    move.origin.check_move_quantity()
        super().receive(shipments)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _compute_component_unit_price(self, unit_price):
        pool = Pool()
        Currency = pool.get('currency.currency')
        UoM = pool.get('product.uom')
        amount, quantity = 0, 0
        for line in self.origin.line.invoice_lines:
            if line.invoice and line.invoice.state in {'posted', 'paid'}:
                with Transaction().set_context(date=self.effective_date):
                    amount += Currency.compute(
                        line.invoice.currency, line.amount, self.currency)
                quantity += UoM.compute_qty(
                    line.unit, line.quantity, self.origin.line.unit)
        amount *= self.origin.price_ratio
        if quantity:
            unit_price = amount / Decimal(str(quantity))
        if unit_price is not None:
            unit_price = UoM.compute_price(
                self.origin.unit, unit_price, self.unit)
            unit_price = round_price(unit_price)
        return unit_price


class MoveSale(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['sale.line.component']

    def get_sale(self, name):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        sale = super().get_sale(name)
        if isinstance(self.origin, SaleLineComponent):
            sale = self.origin.line.sale.id
        return sale

    @classmethod
    def search_sale(cls, name, clause):
        domain = super().search_sale(name, clause)
        return ['OR',
            domain,
            ('origin.line.' + clause[0],
                *clause[1:3], 'sale.line.component', *clause[3:]),
            ]

    def get_sale_exception_state(self, name):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        state = super().get_sale_exception_state(name)
        if isinstance(self.origin, SaleLineComponent):
            if self in self.origin.moves_recreated:
                state = 'recreated'
            elif self in self.origin.moves_ignored:
                state = 'ignored'
        return state

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        category = super().on_change_with_product_uom_category(name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to ship and the quantity to invoice.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, SaleLineComponent)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category
        return category

    def get_cost_price(self, product_cost_price=None):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        Sale = pool.get('sale.sale')
        # For return sale's move use the cost price of the original sale
        if (isinstance(self.origin, SaleLineComponent)
                and self.origin.quantity < 0
                and self.from_location.type != 'storage'
                and self.to_location.type == 'storage'
                and isinstance(self.origin.line.origin, Sale)):
            sale = self.origin.line.origin
            cost = Decimal(0)
            qty = Decimal(0)
            for move in sale.moves:
                if (move.state == 'done'
                        and move.from_location.type == 'storage'
                        and move.to_location.type == 'customer'
                        and move.product == self.product):
                    move_quantity = Decimal(str(move.internal_quantity))
                    cost_price = move.get_cost_price(
                        product_cost_price=move.cost_price)
                    qty += move_quantity
                    cost += cost_price * move_quantity
            if qty:
                product_cost_price = round_price(cost / qty)
        return super().get_cost_price(product_cost_price=product_cost_price)

    @property
    def origin_name(self):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        name = super().origin_name
        if isinstance(self.origin, SaleLineComponent) and self.origin.id >= 0:
            name = self.origin.line.sale.rec_name
        return name

    def _compute_unit_price(self, unit_price):
        pool = Pool()
        SaleLineComponent = pool.get('sale.line.component')
        unit_price = super()._compute_unit_price(unit_price)
        if isinstance(self.origin, SaleLineComponent):
            unit_price = self._compute_component_unit_price(unit_price)
        return unit_price


class MovePurchase(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['purchase.line.component']

    def get_purchase(self, name):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        purchase = super().get_purchase(name)
        if isinstance(self.origin, PurchaseLineComponent):
            purchase = self.origin.line.purchase.id
        return purchase

    @classmethod
    def search_purchase(cls, name, clause):
        domain = super().search_purchase(name, clause)
        return ['OR',
            domain,
            ('origin.line.' + clause[0],
                *clause[1:3], 'purchase.line.component', *clause[3:]),
            ]

    def get_supplier(self, name):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        supplier = super().get_supplier(name)
        if isinstance(self.origin, PurchaseLineComponent):
            supplier = self.origin.line.purchase.party.id
        return supplier

    @classmethod
    def search_supplier(cls, name, clause):
        domain = super().search_supplier(name, clause)
        return ['OR',
            domain,
            ('origin.line.purchase.party' + clause[0][len(name):],
                *clause[1:3], 'purchase.line.component', *clause[3:])]

    def get_purchase_exception_state(self, name):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        state = super().get_purchase_exception_state(name)
        if isinstance(self.origin, PurchaseLineComponent):
            if self in self.origin.moves_recreated:
                state = 'recreated'
            elif self in self.origin.moves_ignored:
                state = 'ignored'
        return state

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        category = super().on_change_with_product_uom_category(name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to ship and the quantity to invoice.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, PurchaseLineComponent)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category
        return category

    @property
    def origin_name(self):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        name = super().origin_name
        if (isinstance(self.origin, PurchaseLineComponent)
                and self.origin.id >= 0):
            name = self.origin.line.purchase.rec_name
        return name

    def _compute_unit_price(self, unit_price):
        pool = Pool()
        PurchaseLineComponent = pool.get('purchase.line.component')
        unit_price = super()._compute_unit_price(unit_price)
        if isinstance(self.origin, PurchaseLineComponent):
            unit_price = self._compute_component_unit_price(unit_price)
        return unit_price
