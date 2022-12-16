# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
from decimal import Decimal

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs

from trytond import backend
from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, If, Bool
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.transaction import Transaction
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import CompanyValueMixin

from .exceptions import BlockedWarning, GroupWarning
from .payment import KINDS


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'
    payment_amount = fields.Function(fields.Numeric('Payment Amount',
            digits=(16,
                If(Bool(Eval('second_currency_digits')),
                    Eval('second_currency_digits', 2),
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('payment_kind'),
                },
            depends=['payment_kind', 'second_currency_digits',
                'currency_digits']), 'get_payment_amount',
        searcher='search_payment_amount')
    payment_currency = fields.Function(fields.Many2One(
            'currency.currency', "Payment Currency"),
        'get_payment_currency')
    payments = fields.One2Many('account.payment', 'line', 'Payments',
        readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            },
        depends=['payment_kind'])
    payment_kind = fields.Function(fields.Selection([
                (None, ''),
                ] + KINDS, 'Payment Kind'), 'get_payment_kind')
    payment_blocked = fields.Boolean('Blocked', readonly=True)
    payment_direct_debit = fields.Boolean("Direct Debit",
        states={
            'invisible': ~(
                (Eval('payment_kind') == 'payable')
                & ((Eval('credit', 0) > 0) | (Eval('debit', 0) < 0))),
            },
        depends=['payment_kind', 'debit', 'credit'],
        help="Check if the line will be paid by direct debit.")

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._buttons.update({
                'pay': {
                    'invisible': ~Eval('payment_kind').in_(
                        list(dict(KINDS).keys())),
                    'depends': ['payment_kind'],
                    },
                'payment_block': {
                    'invisible': Eval('payment_blocked', False),
                    'depends': ['payment_blocked'],
                    },
                'payment_unblock': {
                    'invisible': ~Eval('payment_blocked', False),
                    'depends': ['payment_blocked'],
                    },
                })
        cls._check_modify_exclude.update(
            ['payment_blocked', 'payment_direct_debit'])

    @classmethod
    def default_payment_direct_debit(cls):
        return False

    @classmethod
    def get_payment_amount(cls, lines, name):
        amounts = {}
        for line in lines:
            if (not line.account.type.payable
                    and not line.account.type.receivable):
                amounts[line.id] = None
                continue
            if line.second_currency:
                amount = abs(line.amount_second_currency)
            else:
                amount = abs(line.credit - line.debit)

            for payment in line.payments:
                if payment.state != 'failed':
                    amount -= payment.amount

            amounts[line.id] = amount
        return amounts

    @classmethod
    def search_payment_amount(cls, name, clause):
        pool = Pool()
        Payment = pool.get('account.payment')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = cls.__table__()
        payment = Payment.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        payment_amount = Sum(Coalesce(payment.amount, 0))
        main_amount = Abs(table.credit - table.debit) - payment_amount
        second_amount = Abs(table.amount_second_currency) - payment_amount
        amount = Case((table.second_currency == Null, main_amount),
            else_=second_amount)
        value = cls.payment_amount.sql_format(value)

        query = (table
            .join(payment, type_='LEFT',
            condition=(table.id == payment.line) & (payment.state != 'failed'))
            .join(account, condition=table.account == account.id)
            .join(account_type, condition=account.type == account_type.id)
            .select(table.id,
                where=(account_type.payable | account_type.receivable),
                group_by=(table.id, table.second_currency),
                having=Operator(amount, value)
                ))
        return [('id', 'in', query)]

    def get_payment_currency(self, name):
        if self.second_currency:
            return self.second_currency.id
        elif self.currency:
            return self.currency.id

    def get_payment_kind(self, name):
        if (self.account.type.receivable
                and (self.debit > 0 or self.credit < 0)):
            return 'receivable'
        elif (self.account.type.payable
                and (self.credit > 0 or self.debit < 0)):
            return 'payable'

    @classmethod
    def default_payment_blocked(cls):
        return False

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('payments', None)
        return super(MoveLine, cls).copy(lines, default=default)

    @classmethod
    @ModelView.button_action('account_payment.act_pay_line')
    def pay(cls, lines):
        pass

    @classmethod
    @ModelView.button
    def payment_block(cls, lines):
        pool = Pool()
        Payment = pool.get('account.payment')

        cls.write(lines, {
                'payment_blocked': True,
                })
        draft_payments = [p for l in lines for p in l.payments
            if p.state == 'draft']
        if draft_payments:
            Payment.delete(draft_payments)

    @classmethod
    @ModelView.button
    def payment_unblock(cls, lines):
        cls.write(lines, {
                'payment_blocked': False,
                })


class PayLineStart(ModelView):
    "Pay Line"
    __name__ = 'account.move.line.pay.start'
    date = fields.Date(
        "Date",
        help="When the payments are scheduled to happen.\n"
        "Leave empty to use the lines' maturity dates.")


class PayLineAskJournal(ModelView):
    'Pay Line'
    __name__ = 'account.move.line.pay.ask_journal'
    company = fields.Many2One('company.company', 'Company', readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency', readonly=True)
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ('currency', '=', Eval('currency', -1)),
            ],
        depends=['company', 'currency'])

    journals = fields.One2Many(
        'account.payment.journal', None, 'Journals', readonly=True)


class PayLine(Wizard):
    'Pay Line'
    __name__ = 'account.move.line.pay'
    start = StateView(
        'account.move.line.pay.start',
        'account_payment.move_line_pay_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Pay", 'next_', 'tryton-ok', default=True),
            ])
    next_ = StateTransition()
    ask_journal = StateView('account.move.line.pay.ask_journal',
        'account_payment.move_line_pay_ask_journal_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Pay', 'next_', 'tryton-ok', default=True),
            ])
    pay = StateAction('account_payment.act_payment_form')

    def default_start(self, fields):
        pool = Pool()
        Line = pool.get('account.move.line')
        Warning = pool.get('res.user.warning')

        reverse = {'receivable': 'payable', 'payable': 'receivable'}
        types = {
            kind: {
                'parties': set(),
                'lines': list(),
                }
            for kind in reverse.keys()}
        lines = self.records
        for line in lines:
            for kind in types:
                if getattr(line.account.type, kind):
                    types[kind]['parties'].add(line.party)
                    types[kind]['lines'].append(line)

        for kind in types:
            parties = types[kind]['parties']
            others = Line.search([
                    ('account.type.' + reverse[kind], '=', True),
                    ('party', 'in', [p.id for p in parties]),
                    ('reconciliation', '=', None),
                    ('payment_amount', '!=', 0),
                    ('move_state', '=', 'posted'),
                    ])
            for party in parties:
                party_lines = [l for l in others if l.party == party]
                if not party_lines:
                    continue
                lines = [l for l in types[kind]['lines']
                    if l.party == party]
                warning_name = '%s:%s:%s' % (
                    reverse[kind], party,
                    hashlib.md5(str(lines).encode('utf-8')).hexdigest())
                if Warning.check(warning_name):
                    names = ', '.join(l.rec_name for l in lines[:5])
                    if len(lines) > 5:
                        names += '...'
                    raise GroupWarning(warning_name,
                        gettext('account_payment.msg_pay_line_group',
                            names=names,
                            party=party.rec_name,
                            line=party_lines[0].rec_name))
        return {}

    def _get_journals(self):
        journals = {}
        for journal in getattr(self.ask_journal, 'journals', []):
            journals[self._get_journal_key(journal)] = journal
        if getattr(self.ask_journal, 'journal', None):
            journal = self.ask_journal.journal
            journals[self._get_journal_key(journal)] = journal
        return journals

    def _get_journal_key(self, record):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        Line = pool.get('account.move.line')
        if isinstance(record, Journal):
            return (record.company, record.currency)
        elif isinstance(record, Line):
            company = record.move.company
            currency = record.second_currency or company.currency
            return (company, currency)

    def _missing_journal(self):
        lines = self.records
        journals = self._get_journals()

        for line in lines:
            key = self._get_journal_key(line)
            if key not in journals:
                return key

    def transition_next_(self):
        if self._missing_journal():
            return 'ask_journal'
        else:
            return 'pay'

    def default_ask_journal(self, fields):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        values = {}
        company, currency = self._missing_journal()[:2]
        journals = Journal.search([
                ('company', '=', company),
                ('currency', '=', currency),
                ])
        if len(journals) == 1:
            journal, = journals
            values['journal'] = journal.id
        values['company'] = company.id
        values['currency'] = currency.id
        values['journals'] = [j.id for j in self._get_journals().values()]
        return values

    def get_payment(self, line, journals):
        pool = Pool()
        Payment = pool.get('account.payment')

        if (line.debit > 0) or (line.credit < 0):
            kind = 'receivable'
        else:
            kind = 'payable'
        journal = journals[self._get_journal_key(line)]
        payment = Payment(
            company=line.move.company,
            journal=journal,
            party=line.party,
            kind=kind,
            amount=line.payment_amount,
            line=line,
            )
        date = self.start.date or line.maturity_date
        # Use default value when empty
        if date:
            payment.date = date
        return payment

    def do_pay(self, action):
        pool = Pool()
        Payment = pool.get('account.payment')
        Warning = pool.get('res.user.warning')

        lines = self.records
        journals = self._get_journals()

        payments = []
        for line in lines:
            if line.payment_blocked:
                warning_name = 'blocked:%s' % line
                if Warning.check(warning_name):
                    raise BlockedWarning(warning_name,
                        gettext('account_payment.msg_pay_line_blocked',
                            line=line.rec_name))
            payments.append(self.get_payment(line, journals))
        Payment.save(payments)
        return action, {
            'res_id': [p.id for p in payments],
            }


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    payment_group_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', 'Payment Group Sequence', required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.payment.group'),
                ]))

    @classmethod
    def default_payment_group_sequence(cls, **pattern):
        return cls.multivalue_model(
            'payment_group_sequence').default_payment_group_sequence()


class ConfigurationPaymentGroupSequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Payment Group Sequence"
    __name__ = 'account.configuration.payment_group_sequence'
    payment_group_sequence = fields.Many2One(
        'ir.sequence', "Payment Group Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'account.payment.group'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationPaymentGroupSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('payment_group_sequence')
        value_names.append('payment_group_sequence')
        fields.append('company')
        migrate_property(
            'account.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_payment_group_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account_payment', 'sequence_account_payment_group')
        except KeyError:
            return None


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    payment_direct_debit = fields.Boolean("Direct Debit",
        states={
            'invisible': Eval('type') != 'in',
            'readonly': Eval('state') != 'draft',
            },
        depends=['type', 'state'],
        help="Check if the invoice is paid by direct debit.")

    @classmethod
    def default_payment_direct_debit(cls):
        return False

    @fields.depends('party')
    def on_change_party(self):
        super(Invoice, self).on_change_party()
        if self.party:
            self.payment_direct_debit = self.party.payment_direct_debit

    def _get_move_line(self, date, amount):
        line = super(Invoice, self)._get_move_line(date, amount)
        line.payment_direct_debit = self.payment_direct_debit
        return line

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        context = Transaction().context

        today = Date.today()

        amounts = super(Invoice, cls).get_amount_to_pay(invoices, name)

        if context.get('with_payment', True):
            for invoice in invoices:
                for line in invoice.lines_to_pay:
                    if line.reconciliation:
                        continue
                    if (name == 'amount_to_pay_today'
                            and line.maturity_date
                            and line.maturity_date > today):
                        continue
                    payment_amount = Decimal(0)
                    for payment in line.payments:
                        if payment.state != 'failed':
                            with Transaction().set_context(date=payment.date):
                                payment_amount += Currency.compute(
                                    payment.currency, payment.amount,
                                    invoice.currency)
                    amounts[invoice.id] -= payment_amount
        return amounts
