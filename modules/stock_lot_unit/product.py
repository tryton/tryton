# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    lot_uom = fields.Many2One('product.uom', "Lot UoM",
        domain=[
            ('category', '=', Eval('default_uom_category', -1)),
            ],
        states={
            'invisible': Eval('type') == 'service',
            },
        help="The default unit of measure for lot.")

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 6.8: rename lot_unit to lot_uom
        if (table_h.column_exist('lot_unit')
                and not table_h.column_exist('lot_uom')):
            table_h.column_rename('lot_unit', 'lot_uom')

        super().__register__(module_name)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
