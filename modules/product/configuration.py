# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool

from .product import COST_PRICE_METHODS

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Product Configuration'
    __name__ = 'product.configuration'

    default_cost_price_method = fields.Function(fields.Selection(
            [(None, '')] + COST_PRICE_METHODS, 'Default Cost Method'),
        'get_default_cost_price_method',
        setter='set_default_cost_price_method')

    @classmethod
    def default_default_cost_price_method(cls):
        return cls().get_default_cost_price_method('default_cost_price_method')

    @classmethod
    def _get_product_field(cls, name):
        pool = Pool()
        ModelField = pool.get('ir.model.field')

        for model in ['product.product', 'product.template']:
            fields = ModelField.search([
                    ('model.model', '=', model),
                    ('name', '=', name),
                    ], limit=1)
            if fields:
                return fields[0]

    def get_default_cost_price_method(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        field = self._get_product_field('cost_price_method')
        properties = Property.search([
                ('field', '=', field.id),
                ('res', '=', None),
                ], limit=1)
        if properties:
            prop, = properties
            if prop.value:
                return prop.value.split(',')[1]

    @classmethod
    def set_default_cost_price_method(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        field = cls._get_product_field('cost_price_method')
        properties = Property.search([
                ('field', '=', field.id),
                ('res', '=', None),
                ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': field.id,
                        'value': ',%s' % value,
                        }])
