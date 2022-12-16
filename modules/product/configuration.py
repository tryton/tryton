# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool
from trytond.rpc import RPC

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Product Configuration'
    __name__ = 'product.configuration'

    default_cost_price_method = fields.Function(fields.Selection(
            'get_cost_price_methods', 'Default Cost Method'),
        'get_default_cost_price_method',
        setter='set_default_cost_price_method')

    @classmethod
    def __setup__(cls):
        super(Configuration, cls).__setup__()
        cls.__rpc__['get_cost_price_methods'] = RPC()

    @classmethod
    def default_default_cost_price_method(cls):
        return cls().get_default_cost_price_method('default_cost_price_method')

    @classmethod
    def get_cost_price_methods(cls):
        pool = Pool()
        Template = pool.get('product.template')
        return (Template.fields_get(
                ['cost_price_method'])['cost_price_method']['selection']
            + [(None, '')])

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
