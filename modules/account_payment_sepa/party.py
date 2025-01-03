# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .exceptions import PartyIdentificationdError


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    sepa_creditor_identifier_used = fields.Function(fields.Char(
            'SEPA Creditor Identifier Used'),
        'get_sepa_creditor_identifier_used')
    sepa_mandates = fields.One2Many('account.payment.sepa.mandate', 'party',
        'SEPA Mandates')

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

    def sepa_mandates_for(self, payment):
        for mandate in self.sepa_mandates:
            if mandate.company == payment.company:
                yield mandate


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
            'invisible': Eval('type') != 'es_vat',
            })

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
        elif self.type == 'es_vat':
            identifier['Id'] += self.sepa_es_suffix or '000'
        return identifier


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.sepa.mandate', 'party'),
            ]
