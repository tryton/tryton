# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table

from trytond.config import config
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'product.configuration'

    default_lot_sequence = fields.MultiValue(
        fields.Many2One(
            'ir.sequence', "Default Lot Sequence",
            domain=[
                ('sequence_type', '=',
                    Id('stock_lot', 'sequence_type_stock_lot')),
                ]))


class ConfigurationDefaultLotSequence(ModelSQL, ValueMixin):
    "Product Configuration Default Lot Sequence"
    __name__ = 'product.configuration.default_lot_sequence'
    default_lot_sequence = fields.Many2One(
        'ir.sequence', "Default Lot Sequence",
        domain=[
            ('sequence_type', '=',
                Id('stock_lot', 'sequence_type_stock_lot')),
            ])


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
            })
    lot_sequence = fields.Many2One(
        'ir.sequence', "Lot Sequence",
        domain=[
            ('sequence_type', '=', Id('stock_lot', 'sequence_type_stock_lot')),
            ],
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        help="The sequence used to automatically number lots.")

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

    @classmethod
    def default_lot_sequence(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        sequence = Configuration(1).get_multivalue(
            'default_lot_sequence', **pattern)
        return sequence.id if sequence else None


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def lot_is_required(self, from_, to):
        'Is product lot required for move with "from_" and "to" location ?'
        return any(l.type in (self.lot_required or []) for l in [from_, to])
