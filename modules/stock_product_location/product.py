# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.product import (
    copy_product_filtered, copy_template_filtered)
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Template(copy_template_filtered('locations'), metaclass=PoolMeta):
    __name__ = 'product.template'
    locations = fields.One2Many('stock.product.location', 'template',
        "Default Locations",
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            })


class Product(copy_product_filtered('locations'), metaclass=PoolMeta):
    __name__ = 'product.product'
    locations = fields.One2Many('stock.product.location', 'product',
        "Default Locations",
        domain=[
            ('template', '=', Eval('template', -1)),
            ],
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            })
