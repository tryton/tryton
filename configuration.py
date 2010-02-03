#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    _name = 'party.configuration'

    party_sequence = fields.Property(type='many2one',
            relation='ir.sequence', string='Party Reference Sequence',
            domain=[
                ('company', 'in', [Eval('company'), False]),
                ('code', '=', 'party.party'),
            ], required=True)

Configuration()
