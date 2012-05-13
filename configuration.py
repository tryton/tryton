#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Production Configuration'
    _name = 'production.configuration'
    _description = __doc__

    production_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Production Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company'), False]),
                ('code', '=', 'production'),
                ], required=True))

Configuration()
