# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

payment_direct_debit = fields.Boolean(
    "Direct Debit", help="Check if supplier does direct debit.")


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    payment_direct_debit = fields.MultiValue(payment_direct_debit)
    payment_direct_debits = fields.One2Many(
        'party.party.payment_direct_debit', 'party', "Direct Debits")
    reception_direct_debits = fields.One2Many(
        'party.party.reception_direct_debit', 'party', "Direct Debits",
        help="Fill to debit automatically the customer.")
    payment_identical_parties = fields.Function(
        fields.Many2Many('party.party', None, None, "Identical Parties"),
        'get_payment_identical_parties')

    @classmethod
    def default_payment_direct_debit(cls, **pattern):
        return False

    def get_payment_identical_parties(self, name):
        return [p.id for p in self._payment_identical_parties()]

    def _payment_identical_parties(self):
        return set()

    @classmethod
    def copy(cls, parties, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('reception_direct_debits')
        return super().copy(parties, default=default)


class PartyPaymentDirectDebit(ModelSQL, CompanyValueMixin):
    "Party Payment Direct Debit"
    __name__ = 'party.party.payment_direct_debit'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    payment_direct_debit = payment_direct_debit


class PartyReceptionDirectDebit(
        sequence_ordered(), MatchMixin, ModelView, ModelSQL):
    "Party Reception Direct Debit"
    __name__ = 'party.party.reception_direct_debit'

    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    journal = fields.Many2One(
        'account.payment.journal', "Journal", required=True)
    type = fields.Selection([
            ('line', "Line"),
            ('balance', "Balance"),
            ], "Type", required=True,
        help_selection={
            'line': "Make one payment per line.",
            'balance': "Make a single payment.",
            })
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company', searcher='search_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')
    process_method = fields.Function(
        fields.Selection('get_process_methods', "Process Method"),
        'on_change_with_process_method')

    @classmethod
    def default_type(cls):
        return 'line'

    @fields.depends('journal')
    def on_change_with_company(self, name=None):
        return self.journal.company if self.journal else None

    @classmethod
    def search_company(cls, name, clause):
        nested = clause[0][len(name):]
        return [('journal.' + name + nested, *clause[1:])]

    @fields.depends('journal')
    def on_change_with_currency(self, name=None):
        return self.journal.currency if self.journal else None

    @classmethod
    def get_process_methods(cls):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        name = 'process_method'
        return Journal.fields_get([name])[name]['selection']

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        if self.journal:
            return self.journal.process_method

    @classmethod
    def get_pattern(cls, line, type='line'):
        return {
            'company': line.company.id,
            'currency': line.payment_currency.id,
            'type': type,
            }

    def get_payments(self, line=None, amount=None, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        assert not line or self.type == 'line'
        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        if line:
            date = min(line.maturity_date, date)
            if amount is None:
                amount = line.payment_amount
        if amount:
            for date, amount in self._compute(date, amount):
                yield self._get_payment(line, date, amount)

    def _compute(self, date, amount):
        yield date, amount

    def _get_payment(self, line, date, amount):
        pool = Pool()
        Payment = pool.get('account.payment')
        return Payment(
            company=self.company,
            journal=self.journal,
            kind='receivable',
            party=self.party,
            date=date,
            amount=amount,
            line=line)

    def get_balance_domain(self, date):
        return [
            ['OR',
                ('account.type.receivable', '=', True),
                ('account.type.payable', '=', True),
                ],
            ('party', '=', self.party.id),
            ('payment_currency', '=', self.currency.id),
            ('reconciliation', '=', None),
            ('payment_amount', '!=', 0),
            ('move_state', '=', 'posted'),
            ['OR',
                ('maturity_date', '<=', date),
                ('maturity_date', '=', None),
                ],
            ('payment_blocked', '!=', True),
            ]

    def get_balance_pending_payment_domain(self):
        return [
            ('party', '=', self.party.id),
            ('currency', '=', self.currency.id),
            ('state', 'not in', ['succeeded', 'failed']),
            ('line', '=', None),
            ]


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment', 'party'),
            ('party.party.reception_direct_debit', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Payment = pool.get('account.payment')
        super().check_erase_company(party, company)

        payments = Payment.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['succeeded', 'failed']),
                ])
        if payments:
            raise EraseError(
                gettext('account_payment.msg_erase_party_pending_payment',
                    party=party.rec_name,
                    company=company.rec_name))
