# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


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
    web_shop_urls = fields.One2Many(
        'product.web_shop_url', 'product', "Web Shop URLs", readonly=True)

    @classmethod
    def copy(cls, products, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('web_shops')
        return super().copy(products, default=default)


class ProductURL(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'product.web_shop_url'

    shop = fields.Many2One('web.shop', "Shop", required=True)
    product = fields.Many2One('product.product', "Product", required=True)
    url = fields.Function(fields.Char("Shop URL"), 'get_url')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.update(['shop', 'product'])

    @classmethod
    def table_query(cls):
        return Pool().get('web.shop-product.product').__table__()

    def get_url(self, name):
        return


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'

    web_shops = fields.Many2Many(
        'web.shop-product.category', 'category', 'shop', "Web Shops",
        help="The list of web shops on which the category is published.")

    @classmethod
    def copy(cls, categories, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('web_shops')
        return super().copy(categories, default=default)


class Attribute(metaclass=PoolMeta):
    __name__ = 'product.attribute'

    web_shops = fields.Many2Many(
        'web.shop-product.attribute', 'attribute', 'shop', "Web Shops",
        help="The list of web shops on which the attribute is published.")

    @classmethod
    def copy(cls, attributes, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('web_shops')
        return super().copy(attributes, default=default)


class Image(metaclass=PoolMeta):
    __name__ = 'product.image'

    web_shop = fields.Boolean("Web Shop")

    @classmethod
    def default_web_shop(cls):
        return False

    @classmethod
    def allowed_match_keys(cls):
        return super().allowed_match_keys() | {'web_shop'}

    @classmethod
    def copy(cls, images, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('web_shop', False)
        return super().copy(images, default=default)
