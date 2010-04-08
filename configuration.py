#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Purchase Configuration'
    _name = 'purchase.configuration'
    _description = __doc__

    purchase_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Purchase Reference Sequence', domain=[
            ('company', 'in', [Eval('company'), False]),
            ('code', '=', 'purchase.purchase'),
        ], required=True))

Configuration()
