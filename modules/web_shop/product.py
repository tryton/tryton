# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    web_shops = fields.Many2Many(
        'web.shop-product.product', 'product', 'shop', "Web Shops",
        states={
            'invisible': ~Eval('salable'),
            },
        depends=['salable'],
        help="The list of web shops on which the product is published.")


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'

    web_shops = fields.Many2Many(
        'web.shop-product.category', 'category', 'shop', "Web Shops",
        help="The list of web shops on which the category is published.")


class Attribute(metaclass=PoolMeta):
    __name__ = 'product.attribute'

    web_shops = fields.Many2Many(
        'web.shop-product.attribute', 'attribute', 'shop', "Web Shops",
        help="The list of web shops on which the attribute is published.")
