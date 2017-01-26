# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Sale Configuration'
    __name__ = 'sale.configuration'
    sale_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Sale Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'sale.sale'),
                ], required=True))
    sale_invoice_method = fields.Property(fields.Selection(
            'get_sale_invoice_methods', 'Sale Invoice Method',
            states={
                'required': Bool(Eval('context', {}).get('company')),
                }))
    sale_shipment_method = fields.Property(fields.Selection(
            'get_sale_shipment_methods', 'Sale Shipment Method',
            states={
                'required': Bool(Eval('context', {}).get('company')),
                }))

    @classmethod
    def get_sale_invoice_methods(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        field_name = 'invoice_method'
        return Sale.fields_get([field_name])[field_name]['selection']

    @classmethod
    def get_sale_shipment_methods(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        field_name = 'shipment_method'
        return Sale.fields_get([field_name])[field_name]['selection']
