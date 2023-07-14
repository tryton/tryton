# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    supply_on_sale = fields.Selection([
            (None, "Never"),
            ('stock_first', "Stock First"),
            ('always', "Always"),
            ], "Supply On Sale",
        states={
            'invisible': ~Eval('purchasable') | ~Eval('salable'),
            })

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        migrate_supply_on_sale = (
            table_h.column_exist('supply_on_sale')
            and table_h.column_is_type('supply_on_sale', 'BOOL'))
        if migrate_supply_on_sale:
            table_h.column_rename('supply_on_sale', '_temp_supply_on_sale')
        if cls._history:
            h_table_h = cls.__table_handler__(module, history=True)
            h_table = cls.__table_history__()
            h_migrate_supply_on_sale = (
                h_table_h.column_exist('supply_on_sale')
                and h_table_h.column_is_type('supply_on_sale', 'BOOL'))
            if h_migrate_supply_on_sale:
                h_table_h.column_rename(
                    'supply_on_sale', '_temp_supply_on_sale')

        super().__register__(module)

        # Migration from 6.6: convert supply_on_sale from boolean to selection
        if migrate_supply_on_sale:
            cursor.execute(*table.update(
                    [table.supply_on_sale],
                    ['always'],
                    where=table._temp_supply_on_sale == Literal(True)))
            table_h.drop_column('_temp_supply_on_sale')
        if cls._history and h_migrate_supply_on_sale:
            cursor.execute(*h_table.update(
                    [h_table.supply_on_sale],
                    ['always'],
                    where=h_table._temp_supply_on_sale == Literal(True)))
            h_table_h.drop_column('_temp_supply_on_sale')

    @fields.depends(methods=['_notify_order_point'])
    def on_change_notify(self):
        notifications = super().on_change_notify()
        notifications.extend(self._notify_order_point())
        return notifications

    @fields.depends('id', 'supply_on_sale')
    def _notify_order_point(self):
        pool = Pool()
        try:
            OrderPoint = pool.get('stock.order_point')
        except KeyError:
            return
        if self.supply_on_sale and self.id is not None and self.id >= 0:
            order_points = OrderPoint.search([
                    ('product.template.id', '=', self.id),
                    ('type', '=', 'purchase'),
                    ], limit=6)
            if order_points:
                names = ', '.join(o.rec_name for o in order_points[:5])
                if len(order_points) > 5:
                    names + '...'
                yield ('warning', gettext(
                        'sale_supply'
                        '.msg_template_supply_on_sale_order_point',
                        order_points=names))


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
