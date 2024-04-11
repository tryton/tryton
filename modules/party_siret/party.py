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
        return self._get_identifier(name, {'fr_siren'})

    @classmethod
    def search_siren(cls, name, clause):
        return cls._search_identifier(name, clause, {'fr_siren'})
