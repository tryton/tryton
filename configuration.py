# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import (ModelView, ModelSQL, ModelSingleton, ValueMixin,
    fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = ['Configuration',
    'ConfigurationSequence', 'ConfigurationSaleMethod']
sale_invoice_method = fields.Selection(
    'get_sale_invoice_methods', "Sale Invoice Method")
sale_shipment_method = fields.Selection(
    'get_sale_shipment_methods', "Sale Shipment Method")


def get_sale_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get([field_name])[field_name]['selection']
    return func


def default_func(field_name):
    @classmethod
    def default(cls, **pattern):
        return getattr(
            cls.multivalue_model(field_name),
            'default_%s' % field_name, lambda: None)()
    return default


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Sale Configuration'
    __name__ = 'sale.configuration'
    sale_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Sale Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'sale.sale'),
                ]))
    sale_invoice_method = fields.MultiValue(sale_invoice_method)
    get_sale_invoice_methods = get_sale_methods('invoice_method')
    sale_shipment_method = fields.MultiValue(sale_shipment_method)
    get_sale_shipment_methods = get_sale_methods('shipment_method')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'sale_invoice_method', 'sale_shipment_method'}:
            return pool.get('sale.configuration.sale_method')
        if field == 'sale_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    default_sale_sequence = default_func('sale_sequence')
    default_sale_invoice_method = default_func('sale_invoice_method')
    default_sale_shipment_method = default_func('sale_shipment_method')


class ConfigurationSequence(ModelSQL, CompanyValueMixin):
    "Sale Configuration Sequence"
    __name__ = 'sale.configuration.sequence'
    sale_sequence = fields.Many2One(
        'ir.sequence', "Sale Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'sale.sale'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sale_sequence')
        value_names.append('sale_sequence')
        fields.append('company')
        migrate_property(
            'sale.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_sale_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('sale', 'sequence_sale')
        except KeyError:
            return None


class ConfigurationSaleMethod(ModelSQL, ValueMixin):
    "Sale Configuration Sale Method"
    __name__ = 'sale.configuration.sale_method'
    sale_invoice_method = sale_invoice_method
    get_sale_invoice_methods = get_sale_methods('invoice_method')
    sale_shipment_method = sale_shipment_method
    get_sale_shipment_methods = get_sale_methods('shipment_method')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationSaleMethod, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['sale_invoice_method', 'sale_shipment_method'])
        value_names.extend(['sale_invoice_method', 'sale_shipment_method'])
        migrate_property(
            'sale.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_sale_invoice_method(cls):
        return 'order'

    @classmethod
    def default_sale_shipment_method(cls):
        return 'order'
