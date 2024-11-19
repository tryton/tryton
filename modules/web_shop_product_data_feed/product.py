# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta

AVAILABLE_SYMBOLS = {
    'oz', 'lb', 'mg', 'g', 'kg',
    'floz', 'pt', 'qt', 'gal',
    'ml', 'cl', 'l', 'cbm',
    'in', 'ft', 'yd', 'cm', 'm',
    'sqft', 'sqm',
    'ct',
    }
SYMBOLS = {
    'ft²': 'sqft',
    'm²': 'sqm',
    'u': 'ct',
    }


class UoM(metaclass=PoolMeta):
    __name__ = 'product.uom'

    @property
    def product_data_feed_symbol(self):
        symbol = SYMBOLS.get(self.symbol, self.symbol)
        if symbol in AVAILABLE_SYMBOLS:
            return symbol


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    google_category = fields.Many2One(
        'product.category.google', "Google Category")
    facebook_category = fields.Many2One(
        'product.category.facebook', "Facebook Category")


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'


class CategoryGoogle(ModelSQL, ModelView):
    __name__ = 'product.category.google'

    code = fields.Char("Code", required=True)
    name = fields.Char("Name", required=True, translate=True)


class CategoryFacebook(ModelSQL, ModelView):
    __name__ = 'product.category.facebook'

    code = fields.Char("Code", required=True)
    name = fields.Char("Name", required=True, translate=True)
