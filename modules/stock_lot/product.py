# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.config import config
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    lot_required = fields.MultiSelection([
            ('supplier', "Supplier"),
            ('customer', "Customer"),
            ('lost_found', "Lost and Found"),
            ('storage', "Storage"),
            ('production', "Production"),
            ], "Lot Required",
        help='The type of location for which lot is required.',
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        depends=['type'])

    @classmethod
    def __register__(cls, module):
        connection = Transaction().connection
        cursor = connection.cursor()

        super().__register__(module)

        table_h = cls.__table_handler__(module)
        template_lot_type_table_name = config.get(
            'table', 'product.template-stock.lot.type',
            default='product.template-stock.lot.type' .replace('.', '_'))
        lot_type_table_name = config.get(
            'table', 'stock.lot.type',
            default='stock.lot.type'.replace('.', '_'))

        # Migration from 5.2: fill lot_required
        if (table_h.table_exist(template_lot_type_table_name)
                and table_h.table_exist(lot_type_table_name)):
            table = cls.__table__()
            template_lot_type = Table(template_lot_type_table_name)
            lot_type = Table(lot_type_table_name)

            cursor_select = connection.cursor()
            cursor_select.execute(*template_lot_type.select(
                    template_lot_type.template,
                    distinct_on=template_lot_type.template))
            for template_id, in cursor_select:
                cursor.execute(*template_lot_type
                    .join(lot_type,
                        condition=template_lot_type.type == lot_type.id)
                    .select(
                        lot_type.code,
                        where=template_lot_type.template == template_id))
                value = cls.lot_required.sql_format([t for t, in cursor])
                cursor.execute(*table.update(
                        [table.lot_required], [value],
                        where=table.id == template_id))
            table_h.drop_table('product.template-stock.lot.type',
                template_lot_type_table_name)
            table_h.drop_table('stock.lot.type', lot_type_table_name)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def lot_is_required(self, from_, to):
        'Is product lot required for move with "from_" and "to" location ?'
        return any(l.type in (self.lot_required or []) for l in [from_, to])
