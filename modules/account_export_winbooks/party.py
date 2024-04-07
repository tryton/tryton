# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal
from sql.operators import Equal

from trytond.model import Exclude, fields
from trytond.pool import PoolMeta


class Configuration(metaclass=PoolMeta):
    __name__ = 'party.configuration'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.identifier_types.selection.extend([
                ('winbooks_supplier', "WinBooks Supplier"),
                ('winbooks_customer', "WinBooks Customer"),
                ])


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    winbooks_supplier_identifier = fields.Function(
        fields.Many2One('party.identifier', "WinBooks Supplier Identifier"),
        'get_winbooks_identifier', searcher='search_winbooks_identifier')
    winbooks_customer_identifier = fields.Function(
        fields.Many2One('party.identifier', "WinBooks Customer Identifier"),
        'get_winbooks_identifier', searcher='search_winbooks_identifier')

    def get_winbooks_identifier(self, name):
        return self._get_identifier(name, {name[:-len('_identifier')]})

    @classmethod
    def search_winbooks_identifier(cls, name, clause):
        return cls._search_identifier(
            name, clause, {name[:-len('_identifier')]})


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('winbooks_party_unique',
                Exclude(t, (t.party, Equal),
                    where=t.type.in_(
                        ['winbooks_supplier', 'winbooks_customer'])
                    & (t.active == Literal(True))),
                'account_export_winbooks.'
                'msg_party_identifier_winbooks_party_unique'),
            ('winbooks_code_unique',
                Exclude(t, (t.code, Equal),
                    where=t.type.in_(
                        ['winbooks_supplier', 'winbooks_customer'])
                    & (t.active == Literal(True))),
                'account_export_winbooks.'
                'msg_party_identifier_winbooks_code_unique'),
            ]
