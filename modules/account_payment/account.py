# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, fields
from trytond.pyson import Eval, If, Bool
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.transaction import Transaction

from .payment import KINDS

__all__ = ['MoveLine', 'PayLine', 'PayLineAskJournal', 'Configuration',
    'Invoice']


class MoveLine:
    __metaclass__ = PoolMeta
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
    payments = fields.One2Many('account.payment', 'line', 'Payments',
        readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            },
        depends=['payment_kind'])
    payment_kind = fields.Function(fields.Selection([
                (None, ''),
                ] + KINDS, 'Payment Kind'), 'get_payment_kind',
        searcher='search_payment_kind')
    payment_blocked = fields.Boolean('Blocked', readonly=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._buttons.update({
                'pay': {
                    'invisible': ~Eval('payment_kind').in_(dict(KINDS).keys()),
                    },
                'payment_block': {
                    'invisible': Eval('payment_blocked', False),
                    },
                'payment_unblock': {
                    'invisible': ~Eval('payment_blocked', False),
                    },
                })
        cls._check_modify_exclude.add('payment_blocked')

    @classmethod
    def get_payment_amount(cls, lines, name):
        amounts = {}
        for line in lines:
            if line.account.kind not in ('payable', 'receivable'):
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
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = cls.__table__()
        payment = Payment.__table__()
        account = Account.__table__()

        payment_amount = Sum(Coalesce(payment.amount, 0))
        main_amount = Abs(table.credit - table.debit) - payment_amount
        second_amount = Abs(table.amount_second_currency) - payment_amount
        amount = Case((table.second_currency == Null, main_amount),
            else_=second_amount)
        value = cls.payment_amount.sql_format(value)

        query = table.join(payment, type_='LEFT',
            condition=(table.id == payment.line) & (payment.state != 'failed')
            ).join(account, condition=table.account == account.id
                ).select(table.id,
                    where=account.kind.in_(['payable', 'receivable']),
                    group_by=(table.id, account.kind, table.second_currency),
                    having=Operator(amount, value)
                    )
        return [('id', 'in', query)]

    def get_payment_kind(self, name):
        return self.account.kind if self.account.kind in dict(KINDS) else None

    @classmethod
    def search_payment_kind(cls, name, clause):
        return [('account.kind',) + tuple(clause[1:])]

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
    start = StateTransition()
    ask_journal = StateView('account.move.line.pay.ask_journal',
        'account_payment.move_line_pay_ask_journal_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Pay', 'start', 'tryton-ok', default=True),
            ])
    pay = StateAction('account_payment.act_payment_form')

    @classmethod
    def __setup__(cls):
        super(PayLine, cls).__setup__()
        cls._error_messages.update({
                'blocked': 'The Line "%(line)s" is blocked.',
                })

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
        pool = Pool()
        Line = pool.get('account.move.line')

        lines = Line.browse(Transaction().context['active_ids'])
        journals = self._get_journals()

        for line in lines:
            key = self._get_journal_key(line)
            if key not in journals:
                return key

    def transition_start(self):
        if self._missing_journal():
            return 'ask_journal'
        else:
            return 'pay'

    def default_ask_journal(self, fields):
        values = {}
        company, currency = self._missing_journal()[:2]
        values['company'] = company.id
        values['currency'] = currency.id
        values['journals'] = [j.id for j in self._get_journals().itervalues()]
        return values

    def get_payment(self, line, journals):
        pool = Pool()
        Payment = pool.get('account.payment')

        if (line.debit > 0) or (line.credit < 0):
            kind = 'receivable'
        else:
            kind = 'payable'
        journal = journals[self._get_journal_key(line)]

        return Payment(
            company=line.move.company,
            journal=journal,
            party=line.party,
            kind=kind,
            amount=line.payment_amount,
            line=line,
            )

    def do_pay(self, action):
        pool = Pool()
        Line = pool.get('account.move.line')
        Payment = pool.get('account.payment')

        lines = Line.browse(Transaction().context['active_ids'])
        journals = self._get_journals()

        payments = []
        for line in lines:
            if line.payment_blocked:
                self.raise_user_warning('blocked:%s' % line,
                    'blocked', {
                        'line': line.rec_name,
                        })
            payments.append(self.get_payment(line, journals))
        Payment.save(payments)
        return action, {
            'res_id': [p.id for p in payments],
            }


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    payment_group_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Payment Group Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.payment.group'),
                ], required=True))


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    def get_amount_to_pay(cls, invoices, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()

        amounts = super(Invoice, cls).get_amount_to_pay(invoices, name)

        for invoice in invoices:
            for line in invoice.lines_to_pay:
                if line.reconciliation:
                    continue
                if (name == 'amount_to_pay_today'
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
