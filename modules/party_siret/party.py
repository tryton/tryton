# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    siren = fields.Function(fields.Many2One(
            'party.identifier', "SIREN"),
        'get_siren', searcher='search_siren')

    def get_siren(self, name):
        for identifier in self.identifiers:
            if identifier.type == 'fr_siren':
                return identifier.id

    @classmethod
    def search_siren(cls, name, clause):
        _, operator, value = clause
        domain = [
            ('identifiers', 'where', [
                    ('code', operator, value),
                    ('type', 'in', 'fr_siren'),
                    ]),
            ]
        # Add party without tax identifier
        if ((operator == '=' and value is None)
                or (operator == 'in' and None in value)):
            domain = ['OR',
                domain, [
                    ('identifiers', 'not where', [
                            ('type', '=', 'fr_siren'),
                            ]),
                    ],
                ]
        return domain
