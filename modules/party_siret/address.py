# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Null
from sql.operators import Concat

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    siret = fields.Function(fields.Many2One(
            'party.identifier', "SIRET"),
        'get_siret', searcher='search_siret')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Party = pool.get('party.party')
        Identifier = pool.get('party.identifier')
        cursor = Transaction().connection.cursor()
        party = Party.__table__()
        address = cls.__table__()
        identifier = Identifier.__table__()

        super().__register__(module)

        table_h = cls.__table_handler__(module)
        party_h = Party.__table_handler__(module)

        # Migrate from 6.2: replace siren and siret by identifier
        if party_h.column_exist('siren'):
            cursor.execute(*identifier.insert(
                    [identifier.party,
                        identifier.type, identifier.code,
                        identifier.active],
                    party.select(
                        party.id, Literal('fr_siren'),
                        party.siren, party.active,
                        where=(party.siren != Null)
                        & (party.siren != ''))))
            if table_h.column_exist('siret_nic'):
                cursor.execute(*identifier.insert(
                        [identifier.party, identifier.address,
                            identifier.type, identifier.code,
                            identifier.active],
                        address.join(
                            party, condition=address.party == party.id
                            ).select(
                            address.party, address.id,
                            Literal('fr_siret'),
                            Concat(party.siren, address.siret_nic),
                            address.active,
                            where=(address.siret_nic != Null)
                            & (address.siret_nic != '')
                            & (party.siren != Null)
                            & (party.siren != ''))))
                table_h.drop_column('siret_nic')
            party_h.drop_column('siren')

    def get_siret(self, name):
        for identifier in self.identifiers:
            if identifier.type == 'fr_siret':
                return identifier.id

    @classmethod
    def search_siret(cls, name, clause):
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
