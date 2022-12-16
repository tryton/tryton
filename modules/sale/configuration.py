#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Sale Configuration'
    _name = 'sale.configuration'
    _description = __doc__

    sale_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Sale Reference Sequence', domain=[
            ('company', 'in', [Eval('company'), False]),
            ('code', '=', 'sale.sale'),
        ], required=True))

Configuration()
