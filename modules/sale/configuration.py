#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval, Bool


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Sale Configuration'
    _name = 'sale.configuration'
    _description = __doc__

    sale_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Sale Reference Sequence', domain=[
            ('company', 'in', [Eval('company'), False]),
            ('code', '=', 'sale.sale'),
        ], required=True))
    sale_invoice_method = fields.Property(fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('shipment', 'On Shipment Sent')
    ], 'Sale Invoice Method', states={
        'required': Bool(Eval('company')),
    }))
    sale_shipment_method = fields.Property(fields.Selection([
        ('manual', 'Manual'),
        ('order', 'On Order Confirmed'),
        ('invoice', 'On Invoice Paid'),
    ], 'Sale Shipment Method', states={
        'required': Bool(Eval('company')),
    }))

Configuration()
