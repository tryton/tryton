# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
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
    sale_invoice_method = fields.Property(fields.Selection([
                ('manual', 'Manual'),
                ('order', 'On Order Processed'),
                ('shipment', 'On Shipment Sent')
                ], 'Sale Invoice Method', states={
                'required': Bool(Eval('context', {}).get('company')),
                }))
    sale_shipment_method = fields.Property(fields.Selection([
                ('manual', 'Manual'),
                ('order', 'On Order Processed'),
                ('invoice', 'On Invoice Paid'),
                ], 'Sale Shipment Method', states={
                'required': Bool(Eval('context', {}).get('company')),
                }))
