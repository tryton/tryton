# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Party Configuration'
    __name__ = 'party.configuration'

    party_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Party Sequence', domain=[
                ('code', '=', 'party.party'),
                ['OR',
                    ('company', '=', Eval('context', {}).get('company', -1)),
                    ('company', '=', None),
                    ],
                ]))
    party_lang = fields.Property(fields.Many2One("ir.lang", 'Party Language',
        help=('The value set on this field will preset the language on new '
            'parties')))
