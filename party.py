# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null, Literal
from sql.functions import CurrentTimestamp

import stdnum.eu.at_02 as sepa
import stdnum.exceptions

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.transaction import Transaction

__all__ = ['Party', 'PartyIdentifier']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    sepa_creditor_identifier_used = fields.Function(fields.Char(
            'SEPA Creditor Identifier Used'),
        'get_sepa_creditor_identifier_used')
    sepa_mandates = fields.One2Many('account.payment.sepa.mandate', 'party',
        'SEPA Mandates')

    @classmethod
    def __register__(cls, module_name):
        Identifier = Pool().get('party.identifier')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        identifier = Identifier.__table__()
        super(Party, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.0: Move sepa_creditor_identifier to identifier
        if table.column_exist('sepa_creditor_identifier'):
            select = sql_table.select(Literal(0), CurrentTimestamp(),
                        sql_table.id, Literal('sepa'),
                        sql_table.sepa_creditor_identifier,
                        where=((sql_table.sepa_creditor_identifier != Null)
                            & (sql_table.sepa_creditor_identifier != "")))
            cursor.execute(*identifier.insert(
                    columns=[identifier.create_uid, identifier.create_date,
                        identifier.party, identifier.type, identifier.code],
                    values=select))
            table.drop_column('sepa_creditor_identifier')

    @classmethod
    def copy(cls, parties, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('sepa_mandates', [])
        return super().copy(parties, default=default)

    def get_sepa_creditor_identifier_used(self, name):
        for identifier in self.identifiers:
            if identifier.type == 'sepa':
                return identifier.code


class PartyIdentifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @classmethod
    def __setup__(cls):
        super(PartyIdentifier, cls).__setup__()
        cls.type.selection.append(('sepa', 'SEPA Creditor Identifier'))
        cls._error_messages.update({
                'unique_sepa': ('Party "%(party)s" has more than one '
                    'SEPA Creditor Identifier.'),
                'sepa_invalid': ('The SEPA identifier "%(code)s" on party '
                    '"%(party)s" is not valid.'),
                })

    @fields.depends('party', '_parent_party.identifiers')
    def check_code(self):
        super(PartyIdentifier, self).check_code()
        if self.type == 'sepa':
            for identifier in self.party.identifiers:
                if identifier.type == 'sepa' and self != identifier:
                    self.raise_user_error('unique_sepa', {
                            'invalid_sepa': self.code,
                            'party': self.party.rec_name,
                            })
            if not sepa.is_valid(self.code):
                # Called from pre_validate so party may not be saved yet
                if self.party and self.party.id > 0:
                    party = self.party.rec_name
                else:
                    party = ''
                self.raise_user_error('sepa_invalid', {
                        'code': self.code,
                        'party': party,
                        })

    @fields.depends('type', 'code')
    def on_change_with_code(self):
        code = super(PartyIdentifier, self).on_change_with_code()
        if self.type == 'sepa':
            try:
                return sepa.compact(self.code)
            except stdnum.exceptions.ValidationError:
                pass
        return code
