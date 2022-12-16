# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Null
from sql.functions import CurrentTimestamp

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import PartyIdentificationdError


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
            if identifier.type == 'eu_at_02':
                return identifier.code

    def get_sepa_identifier(self, name):
        pool = Pool()
        Identifier = pool.get('party.identifier')
        for identifier in self.identifiers:
            if identifier.type == name:
                return identifier.sepa_identifier
        else:
            type = dict(Identifier.get_types()).get(name, name)
            raise PartyIdentificationdError(
                gettext('account_payment_sepa.msg_party_no_id',
                    party=self.rec_name,
                    type=type))


class PartyReceptionDirectDebit(metaclass=PoolMeta):
    __name__ = 'party.party.reception_direct_debit'

    sepa_mandate = fields.Many2One(
        'account.payment.sepa.mandate', "Mandate", ondelete='CASCADE',
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        states={
            'invisible': Eval('process_method') != 'sepa',
            'readonly': ~Eval('party') | (Eval('party', -1) < 0),
            })

    def _get_payment(self, line, date, amount):
        payment = super()._get_payment(line, date, amount)
        payment.sepa_mandate = self.sepa_mandate
        return payment


class PartyIdentifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    sepa_es_suffix = fields.Char(
        "SEPA Suffix", size=3,
        states={
            'invisible': Eval('type') != 'es_nif',
            })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        super().__register__(module_name)

        # Migration from 5.4: sepa identifier merged into eu_at_02
        cursor.execute(*sql_table.update(
                columns=[sql_table.type],
                values=['eu_at_02'],
                where=sql_table.type == 'sepa'))

    @property
    def sepa_identifier(self):
        identifier = {
            'Type': 'OrgId',
            'Id': self.code,
            }
        if self.type == 'eu_at_02':
            identifier['Type'] = 'PrvtId'
            identifier['SchmeNm'] = {'Prtry': 'SEPA'}
        elif self.type == 'be_vat':
            identifier['Issr'] = 'KBO-BCE'
        elif self.type == 'es_nif':
            identifier['Id'] += self.sepa_es_suffix or '000'
        return identifier


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.sepa.mandate', 'party'),
            ]
