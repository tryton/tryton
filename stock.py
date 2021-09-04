# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from functools import wraps

from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.product import round_price


def process_sale(moves_field):
    def _process_sale(func):
        @wraps(func)
        def wrapper(cls, shipments):
            pool = Pool()
            Sale = pool.get('sale.sale')
            with Transaction().set_context(_check_access=False):
                sales = set(m.sale for s in cls.browse(shipments)
                    for m in getattr(s, moves_field) if m.sale)
            func(cls, shipments)
            if sales:
                Sale.__queue__.process(sales)
        return wrapper
    return _process_sale


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.outgoing_moves:
                if (move.state == 'cancelled'
                        and isinstance(move.origin, SaleLine)):
                    raise AccessError(
                        gettext('sale.msg_sale_move_reset_draft',
                            move=move.rec_name))

        return super(ShipmentOut, cls).draft(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_sale('outgoing_moves')
    def done(cls, shipments):
        super(ShipmentOut, cls).done(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_sale('outgoing_moves')
    def cancel(cls, shipments):
        super(ShipmentOut, cls).cancel(shipments)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if (move.state == 'cancelled'
                        and isinstance(move.origin, SaleLine)):
                    raise AccessError(
                        gettext('sale.msg_sale_move_reset_draft',
                            move=move.rec_name))

        return super(ShipmentOutReturn, cls).draft(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    @process_sale('incoming_moves')
    def receive(cls, shipments):
        super(ShipmentOutReturn, cls).receive(shipments)


def process_sale_move(func):
    @wraps(func)
    def wrapper(cls, moves):
        pool = Pool()
        Sale = pool.get('sale.sale')
        with Transaction().set_context(_check_access=False):
            sales = set(m.sale for m in cls.browse(moves) if m.sale)
        func(cls, moves)
        if sales:
            Sale.__queue__.process(sales)
    return wrapper


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale', select=True),
        'get_sale', searcher='search_sale')
    sale_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_sale_exception_state')

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models.append('sale.line')
        return models

    @classmethod
    def check_origin_types(cls):
        types = super(Move, cls).check_origin_types()
        types.add('customer')
        return types

    def get_sale(self, name):
        SaleLine = Pool().get('sale.line')
        if isinstance(self.origin, SaleLine):
            return self.origin.sale.id

    @classmethod
    def search_sale(cls, name, clause):
        return [('origin.' + clause[0],) + tuple(clause[1:3])
            + ('sale.line',) + tuple(clause[3:])]

    def get_sale_exception_state(self, name):
        SaleLine = Pool().get('sale.line')
        if not isinstance(self.origin, SaleLine):
            return ''
        if self in self.origin.moves_recreated:
            return 'recreated'
        if self in self.origin.moves_ignored:
            return 'ignored'
        return ''

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        category = super(Move, self).on_change_with_product_uom_category(
            name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to ship and the quantity to invoice.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, SaleLine)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category.id
        return category

    def get_cost_price(self, product_cost_price=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        Sale = pool.get('sale.sale')
        # For return sale's move use the cost price of the original sale
        if (isinstance(self.origin, SaleLine)
                and self.origin.quantity < 0
                and self.from_location.type != 'storage'
                and self.to_location.type == 'storage'
                and isinstance(self.origin.sale.origin, Sale)):
            sale = self.origin.sale.origin
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
        SaleLine = pool.get('sale.line')
        name = super(Move, self).origin_name
        if isinstance(self.origin, SaleLine):
            name = self.origin.sale.rec_name
        return name

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_sale_move
    def cancel(cls, moves):
        super(Move, cls).cancel(moves)

    @classmethod
    @process_sale_move
    def delete(cls, moves):
        super(Move, cls).delete(moves)
