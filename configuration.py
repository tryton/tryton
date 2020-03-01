# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

sale_invoice_grouping_method = fields.Selection(
    'get_sale_invoice_grouping_methods', "Sale Invoice Grouping Method",
    help="The default invoice grouping method for new customers.")


@classmethod
def get_sale_invoice_grouping_methods(cls):
    pool = Pool()
    Party = pool.get('party.party')
    field_name = 'sale_invoice_grouping_method'
    return Party.fields_get([field_name])[field_name]['selection']


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    sale_invoice_grouping_method = fields.MultiValue(
        sale_invoice_grouping_method)
    get_sale_invoice_grouping_methods = get_sale_invoice_grouping_methods

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_invoice_grouping_method':
            return pool.get('sale.configuration.sale_method')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def get_sale_invoice_grouping_methods(cls):
        pool = Pool()
        Party = pool.get('party.party')
        field_name = 'sale_invoice_grouping_method'
        return Party.fields_get([field_name])[field_name]['selection']


class ConfigurationSaleMethod(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sale_method'

    sale_invoice_grouping_method = sale_invoice_grouping_method
    get_sale_invoice_grouping_methods = get_sale_invoice_grouping_methods

    @classmethod
    def get_sale_invoice_grouping_methods(cls):
        pool = Pool()
        Party = pool.get('party.party')
        field_name = 'sale_invoice_grouping_method'
        return Party.fields_get([field_name])[field_name]['selection']
