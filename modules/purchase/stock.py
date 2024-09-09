# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import cached_property
from trytond.transaction import Transaction, without_check_access


def process_purchase(moves_field):
    def _process_purchase(func):
        @wraps(func)
        def wrapper(cls, shipments):
            pool = Pool()
            Purchase = pool.get('purchase.purchase')
            transaction = Transaction()
            context = transaction.context
            with without_check_access():
                purchases = set(m.purchase for s in cls.browse(shipments)
                    for m in getattr(s, moves_field) if m.purchase)
            func(cls, shipments)
            if purchases:
                with transaction.set_context(
                        queue_batch=context.get('queue_batch', True)):
                    Purchase.__queue__.process(purchases)
        return wrapper
    return _process_purchase


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def __setup__(cls):
        super(ShipmentIn, cls).__setup__()
        add_remove = [
            ('supplier', '=', Eval('supplier')),
            ]
        if not cls.incoming_moves.add_remove:
            cls.incoming_moves.add_remove = add_remove
        else:
            cls.incoming_moves.add_remove = [
                add_remove,
                cls.incoming_moves.add_remove,
                ]
        cls.incoming_moves.depends.add('supplier')

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        PurchaseLine = Pool().get('purchase.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if (move.state == 'cancelled'
                        and isinstance(move.origin, PurchaseLine)):
                    raise AccessError(
                        gettext('purchase.msg_purchase_move_reset_draft',
                            move=move.rec_name))

        return super(ShipmentIn, cls).draft(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    @process_purchase('incoming_moves')
    def receive(cls, shipments):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if isinstance(move.origin, PurchaseLine):
                    move.origin.check_move_quantity()
        super(ShipmentIn, cls).receive(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_purchase('incoming_moves')
    def cancel(cls, shipments):
        super(ShipmentIn, cls).cancel(shipments)


class ShipmentInReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        PurchaseLine = Pool().get('purchase.line')
        for shipment in shipments:
            for move in shipment.moves:
                if (move.state == 'cancelled'
                        and isinstance(move.origin, PurchaseLine)):
                    raise AccessError(
                        gettext('purchase.msg_purchase_move_reset_draft',
                            move=move.rec_name))

        return super(ShipmentInReturn, cls).draft(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_purchase('moves')
    def do(cls, shipments):
        super().do(shipments)


def process_purchase_move(without_shipment=False):
    def _process_purchase_move(func):
        @wraps(func)
        def wrapper(cls, moves):
            pool = Pool()
            Purchase = pool.get('purchase.purchase')
            transaction = Transaction()
            context = transaction.context
            with without_check_access():
                p_moves = cls.browse(moves)
                if without_shipment:
                    p_moves = [m for m in p_moves if not m.shipment]
                purchases = set(m.purchase for m in p_moves if m.purchase)
            func(cls, moves)
            if purchases:
                with transaction.set_context(
                        queue_batch=context.get('queue_batch', True)):
                    Purchase.__queue__.process(purchases)
        return wrapper
    return _process_purchase_move


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    purchase = fields.Function(
        fields.Many2One('purchase.purchase', 'Purchase'),
        'get_purchase', searcher='search_purchase')
    supplier = fields.Function(fields.Many2One(
            'party.party', 'Supplier',
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'get_supplier', searcher='search_supplier')
    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if not cls.origin.domain:
            cls.origin.domain = {}
        cls.origin.domain['purchase.line'] = [
            ('type', '=', 'line'),
            ]

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models.append('purchase.line')
        return models

    @classmethod
    def check_origin_types(cls):
        types = super(Move, cls).check_origin_types()
        types.add('supplier')
        return types

    def get_purchase(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if isinstance(self.origin, PurchaseLine):
            return self.origin.purchase.id

    @classmethod
    def search_purchase(cls, name, clause):
        return [('origin.' + clause[0],) + tuple(clause[1:3])
            + ('purchase.line',) + tuple(clause[3:])]

    def get_purchase_exception_state(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if not isinstance(self.origin, PurchaseLine):
            return ''
        if self in self.origin.moves_recreated:
            return 'recreated'
        if self in self.origin.moves_ignored:
            return 'ignored'

    def get_supplier(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if isinstance(self.origin, PurchaseLine):
            return self.origin.purchase.party.id

    @cached_property
    def product_name(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        name = super().product_name
        if (isinstance(self.origin, PurchaseLine)
                and self.origin.product_supplier):
            name = self.origin.product_supplier.rec_name
        return name

    @fields.depends('origin')
    def on_change_with_product_uom_category(self, name=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        category = super(Move, self).on_change_with_product_uom_category(
            name=name)
        # Enforce the same unit category as they are used to compute the
        # remaining quantity to receive and the quantity to invoice.
        # Use getattr as reference field can have negative id
        if (isinstance(self.origin, PurchaseLine)
                and getattr(self.origin, 'unit', None)):
            category = self.origin.unit.category
        return category

    @property
    def origin_name(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        name = super(Move, self).origin_name
        if isinstance(self.origin, PurchaseLine) and self.origin.id >= 0:
            name = self.origin.purchase.rec_name
        return name

    @classmethod
    def search_supplier(cls, name, clause):
        return [('origin.purchase.party' + clause[0][len(name):],
                *clause[1:3], 'purchase.line', *clause[3:])]

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_purchase_move(without_shipment=True)
    def do(cls, moves):
        super().do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_purchase_move(without_shipment=True)
    def cancel(cls, moves):
        super(Move, cls).cancel(moves)

    @classmethod
    @process_purchase_move()
    def delete(cls, moves):
        super(Move, cls).delete(moves)


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    supplier_return_location = fields.Many2One(
        'stock.location', 'Supplier Return',
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id', -1)]),
            ],
        help='If empty the Storage location is used.')
