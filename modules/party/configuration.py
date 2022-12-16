# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Party Configuration'
    __name__ = 'party.configuration'

    party_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Party Sequence', domain=[
                ('code', '=', 'party.party'),
                ]))
