#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval, Bool

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Purchase Configuration'
    __name__ = 'purchase.configuration'
    purchase_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Purchase Reference Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', 0), None]),
                ('code', '=', 'purchase.purchase'),
                ], required=True))
    purchase_invoice_method = fields.Property(fields.Selection([
                ('manual', 'Manual'),
                ('order', 'Based On Order'),
                ('shipment', 'Based On Shipment'),
                ], 'Invoice Method', states={
                'required': Bool(Eval('context', {}).get('company', 0)),
                }))
