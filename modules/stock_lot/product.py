# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id


class Configuration(metaclass=PoolMeta):
    __name__ = 'product.configuration'

    default_lot_sequence = fields.MultiValue(
        fields.Many2One(
            'ir.sequence', "Default Lot Sequence",
            domain=[
                ('sequence_type', '=',
                    Id('stock_lot', 'sequence_type_stock_lot')),
                ('company', '=', None),
                ]))


class ConfigurationDefaultLotSequence(ModelSQL, ValueMixin):
    __name__ = 'product.configuration.default_lot_sequence'
    default_lot_sequence = fields.Many2One(
        'ir.sequence', "Default Lot Sequence",
        domain=[
            ('sequence_type', '=',
                Id('stock_lot', 'sequence_type_stock_lot')),
            ('company', '=', None),
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
            ('company', '=', None),
            ],
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        help="The sequence used to automatically number lots.")

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

    def create_lot(self):
        pool = Pool()
        Lot = pool.get('stock.lot')
        if self.lot_sequence:
            lot = Lot(product=self)
            try:
                lot.on_change_product()
            except AttributeError:
                pass
            return lot
