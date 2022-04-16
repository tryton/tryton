# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from functools import wraps

from sql.aggregate import BoolAnd, Min

from trytond import backend
from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'
    clearing_account = fields.Many2One('account.account', 'Clearing Account',
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('party_required', '=', False),
            ],
        states={
            'required': Bool(Eval('clearing_journal')),
            })
    clearing_journal = fields.Many2One('account.journal', 'Clearing Journal',
        states={
            'required': Bool(Eval('clearing_account')),
            })
    clearing_posting_delay = fields.TimeDelta(
        "Clearing Posting Delay",
        help="Post automatically the clearing moves after the delay.\n"
        "Leave empty for no posting.")

    @classmethod
    def cron_post_clearing_moves(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        if date is None:
            date = Date.today()
        moves = []
        journals = cls.search([
                ('clearing_posting_delay', '!=', None),
                ])
        for journal in journals:
            move_date = date - journal.clearing_posting_delay
            moves.extend(Move.search([
                        ('date', '<=', move_date),
                        ('origin.journal.id', '=', journal.id,
                            'account.payment'),
                        ('state', '=', 'draft'),
                        ('company', '=', Transaction().context.get('company')),
                        ]))
        Move.post(moves)


def cancel_clearing_move(func):
    @wraps(func)
    def wrapper(cls, payments, *args, **kwargs):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')

        func(cls, payments, *args, **kwargs)

        to_delete = []
        to_reconcile = defaultdict(lambda: defaultdict(list))
        to_unreconcile = []
        for payment in payments:
            if payment.clearing_move:
                if payment.clearing_move.state == 'draft':
                    to_delete.append(payment.clearing_move)
                    for line in payment.clearing_move.lines:
                        if line.reconciliation:
                            to_unreconcile.append(line.reconciliation)
                else:
                    cancel_move = payment.clearing_move.cancel()
                    for line in (payment.clearing_move.lines
                            + cancel_move.lines):
                        if line.reconciliation:
                            to_unreconcile.append(line.reconciliation)
                        if line.account.reconcile:
                            to_reconcile[payment.party][line.account].append(
                                line)

        # Remove clearing_move before delete
        # in case reconciliation triggers use it.
        cls.write(payments, {'clearing_move': None})

        if to_unreconcile:
            Reconciliation.delete(to_unreconcile)
        if to_delete:
            Move.delete(to_delete)
        for party in to_reconcile:
            for lines in to_reconcile[party].values():
                Line.reconcile(lines)
        cls.update_reconciled(payments)
    return wrapper


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'
    account = fields.Many2One(
        'account.account', "Account", ondelete='RESTRICT',
        domain=[
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ('type.statement', 'in', ['balance', 'off-balance']),
            ['OR',
                ('second_currency', '=', Eval('currency', None)),
                [
                    ('company.currency', '=', Eval('currency', None)),
                    ('second_currency', '=', None),
                    ],
                ],
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Bool(Eval('line')),
            },
        help="Define the account to use for clearing move.")
    clearing_move = fields.Many2One('account.move', 'Clearing Move',
        readonly=True)
    clearing_reconciled = fields.Boolean(
        "Clearing Reconciled", select=True,
        states={
            'invisible': ~Eval('clearing_move'),
            },
        help="Checked if clearing line is reconciled.")

    @property
    def amount_line_paid(self):
        amount = super().amount_line_paid

        if self.clearing_move:
            clearing_lines = [
                l for l in self.clearing_move.lines
                if l.account == self.clearing_account]
            if clearing_lines:
                clearing_line = clearing_lines[0]
                if (not self.line.reconciliation
                        and clearing_line.reconciliation):
                    if self.line.second_currency:
                        payment_amount = abs(self.line.amount_second_currency)
                    else:
                        payment_amount = abs(
                            self.line.credit - self.line.debit)
                    amount -= max(min(self.amount, payment_amount), 0)
        return amount

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        line_invisible = Bool(Eval('account'))
        if 'invisible' in cls.line.states:
            cls.line.states['invisible'] &= line_invisible
        else:
            cls.line.states['invisible'] = line_invisible
        cls._buttons.update({
                'succeed_wizard': cls._buttons['succeed'],
                })

    @classmethod
    @ModelView.button_action('account_payment_clearing.wizard_succeed')
    def succeed_wizard(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('succeeded')
    def succeed(cls, payments):
        pool = Pool()
        Line = pool.get('account.move.line')

        super(Payment, cls).succeed(payments)

        cls.set_clearing_move(payments)
        to_reconcile = []
        for payment in payments:
            if (payment.line
                    and not payment.line.reconciliation
                    and payment.clearing_move):
                lines = [l for l in payment.clearing_move.lines
                    if l.account == payment.line.account] + [payment.line]
                if not sum(l.debit - l.credit for l in lines):
                    to_reconcile.append(lines)
        Line.reconcile(*to_reconcile)
        cls.reconcile_clearing(payments)
        cls.update_reconciled(payments)

    @property
    def clearing_account(self):
        if self.line:
            return self.line.account
        elif self.account:
            return self.account

    @property
    def clearing_party(self):
        if self.line:
            return self.line.party
        else:
            return self.party

    @classmethod
    def set_clearing_move(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        moves = []
        for payment in payments:
            move = payment._get_clearing_move()
            if move and not payment.clearing_move:
                payment.clearing_move = move
                moves.append(move)
        if moves:
            Move.save(moves)
        cls.save(payments)

    def _get_clearing_move(self, date=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        if not self.clearing_account:
            return
        if (not self.journal.clearing_account
                or not self.journal.clearing_journal):
            return
        if self.clearing_move:
            return self.clearing_move

        if date is None:
            date = Transaction().context.get('clearing_date')
        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        period = Period.find(self.company.id, date=date)

        local_currency = self.journal.currency == self.company.currency
        if not local_currency:
            with Transaction().set_context(date=self.date):
                local_amount = Currency.compute(
                    self.journal.currency, self.amount, self.company.currency)
        else:
            local_amount = self.amount

        move = Move(journal=self.journal.clearing_journal, origin=self,
            date=date, period=period, company=self.company)
        line = Line()
        if self.kind == 'payable':
            line.debit, line.credit = local_amount, 0
        else:
            line.debit, line.credit = 0, local_amount
        line.account = self.clearing_account
        if not local_currency:
            line.amount_second_currency = self.amount.copy_sign(
                line.debit - line.credit)
            line.second_currency = self.journal.currency

        line.party = (self.clearing_party
            if line.account.party_required else None)
        counterpart = Line()
        if self.kind == 'payable':
            counterpart.debit, counterpart.credit = 0, local_amount
        else:
            counterpart.debit, counterpart.credit = local_amount, 0
        counterpart.account = self.journal.clearing_account
        if not local_currency:
            counterpart.amount_second_currency = self.amount.copy_sign(
                counterpart.debit - counterpart.credit)
            counterpart.second_currency = self.journal.currency
        move.lines = (line, counterpart)
        return move

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    @cancel_clearing_move
    def proceed(cls, payments):
        super().proceed(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    @cancel_clearing_move
    def fail(cls, payments):
        super(Payment, cls).fail(payments)

    @classmethod
    def update_reconciled(cls, payments):
        for payment in payments:
            if payment.clearing_move:
                payment.clearing_reconciled = all(
                    l.reconciliation for l in payment.clearing_lines)
            else:
                payment.clearing_reconciled = False
        cls.save(payments)

    @classmethod
    def reconcile_clearing(cls, payments):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Group = pool.get('account.payment.group')
        to_reconcile = []
        for payment in payments:
            if not payment.clearing_move:
                continue
            clearing_account = payment.journal.clearing_account
            if not clearing_account or not clearing_account.reconcile:
                continue
            lines = [l for l in payment.clearing_lines if not l.reconciliation]
            if lines and not sum((l.debit - l.credit) for l in lines):
                to_reconcile.append(lines)
        if to_reconcile:
            MoveLine.reconcile(*to_reconcile)
        Group.reconcile_clearing(
            Group.browse(list({p.group for p in payments if p.group})))

    @property
    def clearing_lines(self):
        clearing_account = self.journal.clearing_account
        if self.clearing_move:
            for line in self.clearing_move.lines:
                if line.account == clearing_account:
                    yield line

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('clearing_move')
        return super(Payment, cls).copy(payments, default=default)


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    clearing_reconciled = fields.Function(fields.Boolean(
            "Clearing Reconciled",
            help="All payments in the group are reconciled."),
        'get_reconciled', searcher='search_reconciled')

    @classmethod
    def get_reconciled(cls, groups, name):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()
        cursor = Transaction().connection.cursor()
        result = defaultdict()
        if backend.name == 'sqlite':
            column = Min(payment.clearing_reconciled)
        else:
            column = BoolAnd(payment.clearing_reconciled)
        for sub_groups in grouped_slice(groups):
            cursor.execute(*payment.select(
                    payment.group, column,
                    where=reduce_ids(payment.group, sub_groups),
                    group_by=payment.group))
            result.update(cursor)
        return result

    @classmethod
    def search_reconciled(cls, name, clause):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        if backend.name == 'sqlite':
            column = Min(payment.clearing_reconciled)
        else:
            column = BoolAnd(payment.clearing_reconciled)

        query = payment.select(
            payment.group,
            having=Operator(column, value),
            group_by=payment.group)
        return [('id', 'in', query)]

    @classmethod
    def reconcile_clearing(cls, groups):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        to_reconcile = []
        for group in groups:
            clearing_account = group.journal.clearing_account
            if not clearing_account or not clearing_account.reconcile:
                continue
            lines = [l for l in group.clearing_lines if not l.reconciliation]
            if lines and not sum((l.debit - l.credit) for l in lines):
                to_reconcile.append(lines)
        if to_reconcile:
            MoveLine.reconcile(*to_reconcile)

    @property
    def clearing_lines(self):
        for payment in self.payments:
            yield from payment.clearing_lines


class Succeed(Wizard):
    "Succeed Payment"
    __name__ = 'account.payment.succeed'
    start = StateView('account.payment.succeed.start',
        'account_payment_clearing.succeed_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Succeed', 'succeed', 'tryton-ok', default=True),
            ])
    succeed = StateTransition()

    def transition_succeed(self):
        with Transaction().set_context(clearing_date=self.start.date):
            self.model.succeed(self.records)
        return 'end'


class SucceedStart(ModelView):
    "Succeed Payment"
    __name__ = 'account.payment.succeed.start'
    date = fields.Date("Date", required=True)

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()
