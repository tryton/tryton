# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, ValueMixin, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.pyson import Eval, Id, TimeDelta

sale_invoice_method = fields.Selection(
    'get_sale_invoice_methods', "Sale Invoice Method")
sale_shipment_method = fields.Selection(
    'get_sale_shipment_methods', "Sale Shipment Method")
sale_quotation_validity = fields.TimeDelta(
    "Sale Quotation Validity",
    domain=['OR',
        ('sale_quotation_validity', '>=', dt.timedelta()),
        ('sale_quotation_validity', '=', None),
        ])


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
    __name__ = 'sale.configuration'
    sale_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Sale Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=', Id('sale', 'sequence_type_sale')),
                ]))
    sale_quotation_validity = fields.MultiValue(sale_quotation_validity)
    sale_invoice_method = fields.MultiValue(sale_invoice_method)
    get_sale_invoice_methods = get_sale_methods('invoice_method')
    sale_shipment_method = fields.MultiValue(sale_shipment_method)
    get_sale_shipment_methods = get_sale_methods('shipment_method')
    sale_process_after = fields.TimeDelta(
        "Process Sale after",
        domain=['OR',
            ('sale_process_after', '=', None),
            ('sale_process_after', '>=', TimeDelta()),
            ],
        help="The grace period during which confirmed sale "
        "can still be reset to draft.\n"
        "Applied if a worker queue is activated.")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'sale_invoice_method', 'sale_shipment_method'}:
            return pool.get('sale.configuration.sale_method')
        if field == 'sale_sequence':
            return pool.get('sale.configuration.sequence')
        elif field == 'sale_quotation_validity':
            return pool.get('sale.configuration.quotation')
        return super().multivalue_model(field)

    default_sale_sequence = default_func('sale_sequence')
    default_sale_invoice_method = default_func('sale_invoice_method')
    default_sale_shipment_method = default_func('sale_shipment_method')


class ConfigurationSequence(ModelSQL, CompanyValueMixin):
    __name__ = 'sale.configuration.sequence'
    sale_sequence = fields.Many2One(
        'ir.sequence', "Sale Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=', Id('sale', 'sequence_type_sale')),
            ])

    @classmethod
    def default_sale_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('sale', 'sequence_sale')
        except KeyError:
            return None


class ConfigurationSaleMethod(ModelSQL, ValueMixin):
    __name__ = 'sale.configuration.sale_method'
    sale_invoice_method = sale_invoice_method
    get_sale_invoice_methods = get_sale_methods('invoice_method')
    sale_shipment_method = sale_shipment_method
    get_sale_shipment_methods = get_sale_methods('shipment_method')

    @classmethod
    def default_sale_invoice_method(cls):
        return 'order'

    @classmethod
    def default_sale_shipment_method(cls):
        return 'order'


class ConfigurationQuotation(ModelSQL, ValueMixin):
    __name__ = 'sale.configuration.quotation'
    sale_quotation_validity = sale_quotation_validity
