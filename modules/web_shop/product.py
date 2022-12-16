# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.config import config
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

if not config.get('html', 'plugins-product.template-web_shop_description'):
    config.set(
        'html', 'plugins-product.template-web_shop_description', 'fullpage')


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    web_shop_description = fields.Text("Web Shop Description", translate=True)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    web_shops = fields.Many2Many(
        'web.shop-product.product', 'product', 'shop', "Web Shops",
        states={
            'invisible': ~Eval('salable'),
            },
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


class Image(metaclass=PoolMeta):
    __name__ = 'product.image'

    web_shop = fields.Boolean("Web Shop")
