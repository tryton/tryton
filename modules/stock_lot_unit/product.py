# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    lot_unit = fields.Many2One('product.uom', "Lot Unit",
        domain=[
            ('category', '=', Eval('default_uom_category', -1)),
            ],
        states={
            'invisible': Eval('type') == 'service',
            },
        depends=['type', 'default_uom_category'],
        help="The default unit for lot.")


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
