# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import (ModelView, ModelSQL, ModelSingleton,
    MultiValueMixin, ValueMixin, fields)
from trytond.pool import Pool
from trytond.tools.multivalue import migrate_property

__all__ = ['Configuration', 'ConfigurationDefaultCostPriceMethod']
default_cost_price_method = fields.Selection(
    'get_cost_price_methods', "Default Cost Method")


@classmethod
def get_cost_price_methods(cls):
    pool = Pool()
    Template = pool.get('product.template')
    field_name = 'cost_price_method'
    return (Template.fields_get([field_name])[field_name]['selection']
        + [(None, '')])


class Configuration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    'Product Configuration'
    __name__ = 'product.configuration'

    default_cost_price_method = fields.MultiValue(default_cost_price_method)
    get_cost_price_methods = get_cost_price_methods

    @classmethod
    def default_default_cost_price_method(cls, **pattern):
        return cls.multivalue_model(
            'default_cost_price_method').default_default_cost_price_method()


class ConfigurationDefaultCostPriceMethod(ModelSQL, ValueMixin):
    "Product Configuration Default Cost Price Method"
    __name__ = 'product.configuration.default_cost_price_method'
    default_cost_price_method = default_cost_price_method
    get_cost_price_methods = get_cost_price_methods

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationDefaultCostPriceMethod, cls).__register__(
            module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('default_cost_price_method')
        value_names.append('default_cost_price_method')
        migrate_property(
            'product.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_default_cost_price_method(cls):
        return 'fixed'
