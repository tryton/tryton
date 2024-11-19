# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, MultiValueMixin, ValueMixin, fields)
from trytond.pool import Pool
from trytond.pyson import Id

default_cost_price_method = fields.Selection(
    'get_cost_price_methods', "Default Cost Method",
    help="The default cost price method for new products.")


@classmethod
def get_cost_price_methods(cls):
    pool = Pool()
    Template = pool.get('product.template')
    field_name = 'cost_price_method'
    return (Template.fields_get([field_name])[field_name]['selection']
        + [(None, '')])


class Configuration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    __name__ = 'product.configuration'

    default_cost_price_method = fields.MultiValue(default_cost_price_method)
    get_cost_price_methods = get_cost_price_methods
    product_sequence = fields.Many2One('ir.sequence', "Variant Sequence",
        domain=[
            ('sequence_type', '=', Id('product', 'sequence_type_product')),
            ],
        help="Used to generate the last part of the product code.")
    template_sequence = fields.Many2One('ir.sequence', "Product Sequence",
        domain=[
            ('sequence_type', '=', Id('product', 'sequence_type_template')),
            ],
        help="Used to generate the first part of the product code.")
    category_sequence = fields.Many2One(
        'ir.sequence', "Category Sequence",
        domain=[
            ('sequence_type', '=', Id('product', 'sequence_type_category')),
            ],
        help="Used to generate the category code.")

    @classmethod
    def default_default_cost_price_method(cls, **pattern):
        return cls.multivalue_model(
            'default_cost_price_method').default_default_cost_price_method()


class ConfigurationDefaultCostPriceMethod(ModelSQL, ValueMixin):
    __name__ = 'product.configuration.default_cost_price_method'
    default_cost_price_method = default_cost_price_method
    get_cost_price_methods = get_cost_price_methods

    @classmethod
    def default_default_cost_price_method(cls):
        return 'fixed'
