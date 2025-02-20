# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Abs

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, fields
from trytond.modules.account.exceptions import (
    CancelWarning, DelegateLineWarning, GroupLineWarning,
    RescheduleLineWarning)
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction, check_access, without_check_access
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import BlockedWarning, GroupWarning
from .payment import KINDS


def _payment_amount_expression(table):
    return (Case(
            (table.second_currency == Null,
                Abs(table.credit - table.debit)),
            else_=Abs(table.amount_second_currency))
        - Coalesce(table.payment_amount_cache, 0))


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    payment_amount = fields.Function(Monetary(
            "Amount to Pay",
            currency='payment_currency', digits='payment_currency',
            states={
                'invisible': ~Eval('payment_kind'),
                }),
        'get_payment_amount')
    payment_amount_cache = Monetary(
        "Amount to Pay Cache",
        currency='payment_currency', digits='payment_currency', readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            })
    payment_currency = fields.Function(fields.Many2One(
            'currency.currency', "Payment Currency"),
        'get_payment_currency', searcher='search_payment_currency')
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
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t, (_payment_amount_expression(t), Index.Range())),
                })
        cls._buttons.update({
                'pay': {
                    'invisible': (
                        ~Eval('payment_kind').in_(list(dict(KINDS).keys()))
                        | Eval('reconciliation')),
                    'depends': ['payment_kind'],
                    },
                'payment_block': {
                    'invisible': (
                        ~Eval('payment_kind').in_(list(dict(KINDS).keys()))
                        | Eval('reconciliation')
                        | Eval('payment_blocked', False)),
                    'depends': ['payment_blocked'],
                    },
                'payment_unblock': {
                    'invisible': (
                        ~Eval('payment_kind').in_(list(dict(KINDS).keys()))
                        | Eval('reconciliation')
                        | ~Eval('payment_blocked', False)),
                    'depends': ['payment_blocked'],
                    },
                })
        cls._check_modify_exclude.update(
            ['payment_blocked', 'payment_direct_debit',
                'payment_amount_cache'])

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        set_payment_amount = not table_h.column_exist('payment_amount')

        super().__register__(module)

        # Migration from 7.2: store payment_amount
        if set_payment_amount:
            cls.set_payment_amount()

    @classmethod
    def default_payment_direct_debit(cls):
        return False

    def get_payment_amount(self, name):
        if self.account.type.payable or self.account.type.receivable:
            if self.second_currency:
                amount = abs(self.amount_second_currency)
            else:
                amount = abs(self.credit - self.debit)
            if self.payment_amount_cache:
                amount -= self.payment_amount_cache
        else:
            amount = None
        return amount

    @classmethod
    def domain_payment_amount(cls, domain, tables):
        pool = Pool()
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        account = Account.__table__()
        account_type = AccountType.__table__()

        table, _ = tables[None]

        accounts = (account
            .join(account_type, condition=account.type == account_type.id)
            .select(
                account.id,
                where=account_type.payable | account_type.receivable))

        _, operator, operand = domain
        Operator = fields.SQL_OPERATORS[operator]

        payment_amount = _payment_amount_expression(table)

        expression = Operator(payment_amount, operand)
        expression &= table.account.in_(accounts)
        return expression

    @classmethod
    def order_payment_amount(cls, tables):
        table, _ = tables[None]
        return [_payment_amount_expression(table)]

    @classmethod
    @without_check_access
    def set_payment_amount(cls, lines=None):
        pool = Pool()
        Payment = pool.get('account.payment')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        payment = Payment.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        accounts = (account
            .join(account_type, condition=account.type == account_type.id)
            .select(
                account.id,
                where=account_type.payable | account_type.receivable))

        query = (table.update(
                [table.payment_amount_cache],
                [payment.select(
                        Sum(Coalesce(payment.amount, 0)),
                        where=(payment.line == table.id)
                        & (payment.state != 'failed'))],
                where=table.account.in_(accounts)))

        if lines:
            for sub_lines in grouped_slice(lines):
                query.where = (
                    table.account.in_(accounts)
                    & reduce_ids(table.id, map(int, sub_lines)))
                cursor.execute(*query)
        else:
            cursor.execute(*query)

        if lines:
            # clear cache
            cls.write(lines, {})

    def get_payment_currency(self, name):
        if self.second_currency:
            return self.second_currency.id
        elif self.currency:
            return self.currency.id

    @classmethod
    def search_payment_currency(cls, name, clause):
        return ['OR',
            [('second_currency', *clause[1:]),
                ('second_currency', '!=', None),
                ],
            [('currency', *clause[1:]),
                ('second_currency', '=', None)],
            ]

    def get_payment_kind(self, name):
        if self.account.type.receivable or self.account.type.payable:
            if self.debit > 0 or self.credit < 0:
                return 'receivable'
            elif self.credit > 0 or self.debit < 0:
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
            ['OR',
                ('maturity_date', '<=', date),
                ('maturity_date', '=', None),
                ],
            ('payment_blocked', '!=', True),
            ]

    @classmethod
    def pay_direct_debit(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Payment = pool.get('account.payment')
        Reception = pool.get('party.party.reception_direct_debit')
        if date is None:
            date = Date.today()
        with check_access():
            lines = cls.search(cls._pay_direct_debit_domain(date))

        payments, receptions = [], set()
        for line in lines:
            if not line.payment_amount:
                # SQLite fails to search for payment_amount != 0
                continue
            pattern = Reception.get_pattern(line)
            for reception in line.party.reception_direct_debits:
                if reception.match(pattern):
                    payments.extend(
                        reception.get_payments(line=line, date=date))
                    break
            else:
                pattern = Reception.get_pattern(line, 'balance')
                for reception in line.party.reception_direct_debits:
                    if reception.match(pattern):
                        receptions.add(reception)
                        break
        Payment.save(payments)

        balance_payments = []
        for reception in receptions:
            lines = cls.search(reception.get_balance_domain(date))
            amount = (
                sum(l.payment_amount for l in lines
                    if l.payment_kind == 'receivable')
                - sum(l.payment_amount for l in lines
                    if l.payment_kind == 'payable'))
            pending_payments = Payment.search(
                reception.get_balance_pending_payment_domain())
            amount -= (
                sum(p.amount for p in pending_payments
                    if p.kind == 'receivable')
                - sum(p.amount for p in pending_payments
                    if p.kind == 'payable'))
            if amount > 0:
                balance_payments.extend(
                    reception.get_payments(amount=amount, date=date))
        Payment.save(balance_payments)
        return payments + balance_payments


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
        action['domains'] = []
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
    payment_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Payment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('account_payment',
                        'sequence_type_account_payment')),
                ]))
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
    def default_payment_sequence(cls, **pattern):
        return cls.multivalue_model(
            'payment_sequence').default_payment_sequence()

    @classmethod
    def default_payment_group_sequence(cls, **pattern):
        return cls.multivalue_model(
            'payment_group_sequence').default_payment_group_sequence()


class ConfigurationPaymentSequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Payment Sequence"
    __name__ = 'account.configuration.payment_sequence'
    payment_sequence = fields.Many2One(
        'ir.sequence', "Payment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('account_payment', 'sequence_type_account_payment')),
            ])

    @classmethod
    def default_payment_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account_payment', 'sequence_account_payment')
        except KeyError:
            return None


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
    def default_payment_group_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account_payment', 'sequence_account_payment_group')
        except KeyError:
            return None


class MoveCancel(metaclass=PoolMeta):
    __name__ = 'account.move.cancel'

    def transition_cancel(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        moves_w_payments = []
        for move in self.records:
            for line in move.lines:
                if any(p.state != 'failed' for p in line.payments):
                    moves_w_payments.append(move)
                    break
        if moves_w_payments:
            names = ', '.join(
                m.rec_name for m in moves_w_payments[:5])
            if len(moves_w_payments) > 5:
                names += '...'
            key = Warning.format('cancel_payments', moves_w_payments)
            if Warning.check(key):
                raise CancelWarning(
                    key, gettext(
                        'account_payment.msg_move_cancel_payments',
                        moves=names))
        return super().transition_cancel()


class MoveLineGroup(metaclass=PoolMeta):
    __name__ = 'account.move.line.group'

    def do_group(self, action):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        lines_w_payments = []
        for line in self.records:
            if any(p.state != 'failed' for p in line.payments):
                lines_w_payments.append(line)
        if lines_w_payments:
            names = ', '.join(
                m.rec_name for m in lines_w_payments[:5])
            if len(lines_w_payments) > 5:
                names += '...'
            key = Warning.format('group_payments', lines_w_payments)
            if Warning.check(key):
                raise GroupLineWarning(
                    key, gettext(
                        'account_payment.msg_move_line_group_payments',
                        lines=names))
        return super().do_group(action)


class MoveLineReschedule(metaclass=PoolMeta):
    __name__ = 'account.move.line.reschedule'

    def do_reschedule(self, action):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        lines_w_payments = []
        for line in self.records:
            if any(p.state != 'failed' for p in line.payments):
                lines_w_payments.append(line)
        if lines_w_payments:
            names = ', '.join(
                m.rec_name for m in lines_w_payments[:5])
            if len(lines_w_payments) > 5:
                names += '...'
            key = Warning.format('reschedule_payments', lines_w_payments)
            if Warning.check(key):
                raise RescheduleLineWarning(
                    key, gettext(
                        'account_payment.msg_move_line_reschedule_payments',
                        lines=names))
        return super().do_reschedule(action)


class MoveLineDelegate(metaclass=PoolMeta):
    __name__ = 'account.move.line.delegate'

    def do_delegate(self, action):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        lines_w_payments = []
        for line in self.records:
            if any(p.state != 'failed' for p in line.payments):
                lines_w_payments.append(line)
        if lines_w_payments:
            names = ', '.join(
                m.rec_name for m in lines_w_payments[:5])
            if len(lines_w_payments) > 5:
                names += '...'
            key = Warning.format('delegate_payments', lines_w_payments)
            if Warning.check(key):
                raise DelegateLineWarning(
                    key, gettext(
                        'account_payment.msg_move_line_delegate_payments',
                        lines=names))
        return super().do_delegate(action)


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


class Statement(metaclass=PoolMeta):
    __name__ = 'account.statement'

    @classmethod
    def create_move(cls, statements):
        moves = super().create_move(statements)
        cls._process_payments(moves)
        return moves

    @classmethod
    def _process_payments(cls, moves):
        pool = Pool()
        Payment = pool.get('account.payment')

        to_success = defaultdict(set)
        to_fail = defaultdict(set)
        for move, statement, lines in moves:
            for line in lines:
                for kind, payments in line.payments():
                    if (kind == 'receivable') == (line.amount >= 0):
                        to_success[line.date].update(payments)
                    else:
                        to_fail[line.date].update(payments)
        # The failing should be done last because success is usually not a
        # definitive state
        if to_success:
            for date, payments in to_success.items():
                with Transaction().set_context(clearing_date=date):
                    Payment.succeed(Payment.browse(payments))
        if to_fail:
            for date, payments in to_fail.items():
                with Transaction().set_context(clearing_date=date):
                    Payment.fail(Payment.browse(payments))
        if to_success or to_fail:
            payments = set.union(*to_success.values(), *to_fail.values())
        else:
            payments = []
        return list(payments)


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.related_to.domain['account.payment'] = [
            ('company', '=', Eval('company', -1)),
            If(Bool(Eval('party')),
                ('party', '=', Eval('party', -1)),
                ()),
            ('state', 'in', ['processing', 'succeeded', 'failed']),
            If(Eval('second_currency'),
                ('currency', '=', Eval('second_currency', -1)),
                ('currency', '=', Eval('currency', -1))),
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

    @fields.depends('party', methods=['payment'])
    def on_change_party(self):
        super(StatementLine, self).on_change_party()
        if self.payment:
            if self.payment.party != self.party:
                self.payment = None

    def payments(self):
        "Yield payments per kind"
        if self.payment:
            yield self.payment.kind, [self.payment]


class StatementRule(metaclass=PoolMeta):
    __name__ = 'account.statement.rule'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.description.help += "\n'payment'"


class StatementRuleLine(metaclass=PoolMeta):
    __name__ = 'account.statement.rule.line'

    def _get_related_to(self, origin, keywords, party=None, amount=0):
        return super()._get_related_to(
            origin, keywords, party=party, amount=amount) | {
            self._get_payment(origin, keywords, party=party, amount=amount),
            }

    def _get_party_from(self, related_to):
        pool = Pool()
        Payment = pool.get('account.payment')
        party = super()._get_party_from(related_to)
        if isinstance(related_to, Payment):
            party = related_to.party
        return party

    @classmethod
    def _get_payment_domain(cls, payment, origin):
        return [
            ('rec_name', '=', payment),
            ('company', '=', origin.company.id),
            ('currency', '=', origin.currency.id),
            ('state', 'in', ['processing', 'succeeded', 'failed']),
            ]

    def _get_payment(self, origin, keywords, party=None, amount=0):
        pool = Pool()
        Payment = pool.get('account.payment')
        if keywords.get('payment'):
            domain = self._get_payment_domain(keywords['payment'], origin)
            if party:
                domain.append(('party', '=', party.id))
            if amount > 0:
                domain.append(('kind', '=', 'receivable'))
            elif amount < 0:
                domain.append(('kind', '=', 'payable'))
            payments = Payment.search(domain)
            if len(payments) == 1:
                payment, = payments
                return payment


class Dunning(metaclass=PoolMeta):
    __name__ = 'account.dunning'

    def get_active(self, name):
        return super().get_active(name) and self.line.payment_amount > 0

    @classmethod
    def search_active(cls, name, clause):
        if tuple(clause[1:]) in [('=', True), ('!=', False)]:
            domain = ('line.payment_amount', '>', 0)
        elif tuple(clause[1:]) in [('=', False), ('!=', True)]:
            domain = ('line.payment_amount', '<=', 0)
        else:
            domain = []
        return [super().search_active(name, clause), domain]

    @classmethod
    def _overdue_line_domain(cls, date):
        return [super()._overdue_line_domain(date),
            ('payment_amount', '>', 0),
            ]
