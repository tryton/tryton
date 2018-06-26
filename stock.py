# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.operators import Concat

from trytond.model import Workflow, ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend

__all__ = ['ShipmentOut', 'ShipmentOutReturn', 'Move']


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft a move generated '
                    'by a sale.'),
                })

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(ShipmentOut, cls).write(*args)

        actions = iter(args)
        for shipments, values in zip(actions, actions):
            if values.get('state') not in ('done', 'cancel'):
                continue
            sales = []
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.outgoing_moves])

            with Transaction().set_context(_check_access=False):
                sale_lines = SaleLine.search([
                        ('moves', 'in', move_ids),
                        ])
                if sale_lines:
                    sales = list(set(l.sale for l in sale_lines))
                    Sale.process(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.outgoing_moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, SaleLine)):
                    cls.raise_user_error('reset_move')

        return super(ShipmentOut, cls).draft(shipments)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft a move generated '
                    'by a sale.'),
                })

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(ShipmentOutReturn, cls).write(*args)

        actions = iter(args)
        for shipments, values in zip(actions, actions):
            if values.get('state') != 'received':
                continue
            sales = []
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.incoming_moves])

            with Transaction().set_context(_check_access=False):
                sale_lines = SaleLine.search([
                        ('moves', 'in', move_ids),
                        ])
                if sale_lines:
                    for sale_line in sale_lines:
                        if sale_line.sale not in sales:
                            sales.append(sale_line.sale)

                    sales = Sale.browse([s.id for s in sales])
                    Sale.process(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        SaleLine = Pool().get('sale.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, SaleLine)):
                    cls.raise_user_error('reset_move')

        return super(ShipmentOutReturn, cls).draft(shipments)


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
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Move, cls).__register__(module_name)

        table = TableHandler(cls, module_name)

        # Migration from 2.6: remove sale_line
        if table.column_exist('sale_line'):
            cursor.execute(*sql_table.update(
                    columns=[sql_table.origin],
                    values=[Concat('sale.line,', sql_table.sale_line)],
                    where=sql_table.sale_line != Null))
            table.drop_column('sale_line')

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

    @property
    def origin_name(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        name = super(Move, self).origin_name
        if isinstance(self.origin, SaleLine):
            name = self.origin.sale.reference or self.origin.sale.rec_name
        return name

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, moves):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        super(Move, cls).cancel(moves)

        sale_lines = SaleLine.search([
                ('moves', 'in', [m.id for m in moves]),
                ])
        if sale_lines:
            sale_ids = list(set(l.sale.id for l in sale_lines))
            sales = Sale.browse(sale_ids)
            Sale.process(sales)

    @classmethod
    def delete(cls, moves):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        with Transaction().set_context(_check_access=False):
            sale_lines = SaleLine.search([
                    ('moves', 'in', [m.id for m in moves]),
                    ])

        super(Move, cls).delete(moves)

        if sale_lines:
            sales = list(set(l.sale for l in sale_lines))
            with Transaction().set_context(_check_access=False):
                Sale.process(sales)
