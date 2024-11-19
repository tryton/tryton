# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

product_recommendation_method = fields.Selection([
        (None, ""),
        ], "Method")
product_recommendation_size = fields.Integer(
    "Size", required=True,
    domain=[
        ('product_recommendation_size', '>=', 0),
        ])


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    product_recommendation_method = fields.MultiValue(
        product_recommendation_method)
    product_recommendation_size = fields.MultiValue(
        product_recommendation_size)

    @classmethod
    def default_product_recommendation_size(cls, **pattern):
        return (
            cls.multivalue_model('product_recommendation_size')
            .default_product_recommendation_size())

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {
                'product_recommendation_method',
                'product_recommendation_size',
                }:
            return pool.get('sale.configuration.product_recommendation')
        return super().multivalue_model(field)


class ConfigurationProductRecommendation(ModelSQL, ValueMixin):
    __name__ = 'sale.configuration.product_recommendation'

    product_recommendation_method = fields.Selection(
        'get_product_recommendation_methods', "Product Recommendation Method")
    product_recommendation_size = product_recommendation_size

    @classmethod
    def get_product_recommendation_methods(cls):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        field_name = 'product_recommendation_method'
        return Configuration.fields_get(
            [field_name])[field_name]['selection']

    @classmethod
    def default_product_recommendation_size(cls):
        return 5


class SaleMixin:
    __slots__ = ()

    recommended_products = fields.Function(fields.Many2Many(
            'product.product', None, None, "Recommended Products",
            states={
                'invisible': (
                    (Eval('state') != 'draft')
                    | ~Eval('recommended_products')),
                }),
        'on_change_with_recommended_products')

    @fields.depends('state')
    def on_change_with_recommended_products(self, name=None):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        if self.state != 'draft':
            return []
        config = Configuration(1)
        method = config.get_multivalue('product_recommendation_method')
        size = config.get_multivalue('product_recommendation_size')
        products = []
        if method:
            generator = getattr(self, '_recommended_products_%s' % method)()
            for product in filter(self._is_recommendable_product, generator):
                products.append(product)
                if len(products) >= size:
                    break
        return products

    @classmethod
    def _is_recommendable_product(cls, product):
        return product.active and product.salable and product.recommendable


class Sale(SaleMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'


class POSSale(SaleMixin, metaclass=PoolMeta):
    __name__ = 'sale.point.sale'
