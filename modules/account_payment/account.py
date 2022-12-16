# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import groupby

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs

from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools.multivalue import migrate_property
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import BlockedWarning, GroupWarning
from .payment import KINDS


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'
    payment_amount = fields.Function(Monetary(
            "Payment Amount",
            currency='payment_currency', digits='payment_currency',
            states={
                'invisible': ~Eval('payment_kind'),
                }),
        'get_payment_amount', searcher='search_payment_amount')
    payment_currency = fields.Function(fields.Many2One(
            'currency.currency', "Payment Currency"),
        'get_payment_currency')
    payments = fields.One2Many('account.payment', 'line', 'Payments',
        readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            })
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
        value = cls.payment_amount._field.sql_cast(
            cls.payment_amount.sql_format(value))

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

    @classmethod
    def _pay_direct_debit_domain(cls, date):
        return [
            ['OR',
                ('account.type.receivable', '=', True),
                ('account.type.payable', '=', True),
                ],
            ('party', '!=', None),
            ('reconciliation', '=', None),
            ('payment_amount', '!=', 0),
            ('move_state', '=', 'posted'),
            ['OR',
                ('debit', '>', 0),
                ('credit', '<', 0),
                ],
            ('maturity_date', '<=', date),
            ]

    @classmethod
    def pay_direct_debit(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Payment = pool.get('account.payment')
        Reception = pool.get('party.party.reception_direct_debit')
        if date is None:
            date = Date.today()
        with Transaction().set_context(_check_access=True):
            lines = cls.search(cls._pay_direct_debit_domain(date))

        payments = []
        for line in lines:
            if not line.payment_amount:
                # SQLite fails to search for payment_amount != 0
                continue
            pattern = Reception.get_pattern(line)
            for reception in line.party.reception_direct_debits:
                if reception.match(pattern):
                    payments.extend(reception.get_payments(line))
        Payment.save(payments)
        return payments


class CreateDirectDebit(Wizard):
    "Create Direct Debit"
    __name__ = 'account.move.line.create_direct_debit'

    start = StateView('account.move.line.create_direct_debit.start',
        'account_payment.move_line_create_direct_debit_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_payment.act_payment_form')

    def do_create_(self, action):
        pool = Pool()
        Line = pool.get('account.move.line')
        payments = Line.pay_direct_debit(date=self.start.date)
        return action, {
            'res_id': [p.id for p in payments],
            }


class CreateDirectDebitStart(ModelView):
    "Create Direct Debit"
    __name__ = 'account.move.line.create_direct_debit.start'

    date = fields.Date(
        "Date", required=True,
        help="Create direct debit for lines due up to this date.")

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()


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
            ])

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
        companies = {}
        lines = self.records
        for line in lines:
            types = companies.setdefault(line.move.company, {
                    kind: {
                        'parties': set(),
                        'lines': list(),
                        }
                    for kind in reverse.keys()})
            for kind in types:
                if getattr(line.account.type, kind):
                    types[kind]['parties'].add(line.party)
                    types[kind]['lines'].append(line)

        for company, types in companies.items():
            for kind in types:
                parties = types[kind]['parties']
                others = Line.search([
                        ('move.company', '=', company.id),
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
                    warning_name = Warning.format(
                        '%s:%s' % (reverse[kind], party), lines)
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
        payment.date = self.start.date or line.maturity_date
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
                ('sequence_type', '=',
                    Id('account_payment',
                        'sequence_type_account_payment_group')),
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
            ('sequence_type', '=',
                Id('account_payment', 'sequence_type_account_payment_group')),
            ])

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

        amounts = super(Invoice, cls).get_amount_to_pay(invoices, name)

        if context.get('with_payment', True):
            for company, c_invoices in groupby(
                    invoices, key=lambda i: i.company):
                with Transaction().set_context(company=company.id):
                    today = Date.today()
                for invoice in c_invoices:
                    for line in invoice.lines_to_pay:
                        if line.reconciliation:
                            continue
                        if (name == 'amount_to_pay_today'
                                and line.maturity_date
                                and line.maturity_date > today):
                            continue
                        payment_amount = Decimal(0)
                        for payment in line.payments:
                            with Transaction().set_context(date=payment.date):
                                payment_amount += Currency.compute(
                                    payment.currency, payment.amount_line_paid,
                                    invoice.currency)
                        amounts[invoice.id] -= payment_amount
        return amounts


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.related_to.domain['account.payment'] = [
            ('company', '=', Eval('company', -1)),
            If(Bool(Eval('party')),
                ('party', '=', Eval('party')),
                ()),
            ('state', 'in', ['processing', 'succeeded', 'failed']),
            ('currency', '=', Eval('currency', -1)),
            ('kind', '=',
                If(Eval('amount', 0) > 0, 'receivable',
                    If(Eval('amount', 0) < 0, 'payable', ''))),
            ]
        cls.related_to.search_order['account.payment'] = [
            ('amount', 'ASC'),
            ('state', 'ASC'),
            ]
        cls.related_to.search_context.update({
                'amount_order': Eval('amount', 0),
                })

    @classmethod
    def _get_relations(cls):
        return super()._get_relations() + ['account.payment']

    @property
    @fields.depends('related_to')
    def payment(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        related_to = getattr(self, 'related_to', None)
        if isinstance(related_to, Payment) and related_to.id >= 0:
            return related_to

    @payment.setter
    def payment(self, value):
        self.related_to = value

    @fields.depends(
        'party', 'statement', '_parent_statement.journal',
        methods=['payment'])
    def on_change_related_to(self):
        super().on_change_related_to()
        if self.payment:
            if not self.party:
                self.party = self.payment.party
            if self.payment.line:
                self.account = self.payment.line.account


class Dunning(metaclass=PoolMeta):
    __name__ = 'account.dunning'

    def get_active(self, name):
        return super().get_active(name) and self.line.payment_amount > 0

    @classmethod
    def search_active(cls, name, clause):
        if tuple(clause[1:]) in {('=', True), ('!=', False)}:
            domain = ('line.payment_amount', '>', 0)
        elif tuple(clause[1:]) in {('=', False), ('!=', True)}:
            domain = ('line.payment_amount', '<=', 0)
        else:
            domain = []
        return [super().search_active(name, clause), domain]

    @classmethod
    def _overdue_line_domain(cls, date):
        return [super()._overdue_line_domain(date),
            ('payment_amount', '>', 0),
            ]
