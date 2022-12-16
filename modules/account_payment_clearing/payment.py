# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

__all__ = ['Journal', 'Payment', 'Succeed', 'SucceedStart']


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'
    clearing_account = fields.Many2One('account.account', 'Clearing Account',
        domain=[('party_required', '=', False)],
        states={
            'required': Bool(Eval('clearing_journal')),
            },
        depends=['clearing_journal'])
    clearing_journal = fields.Many2One('account.journal', 'Clearing Journal',
        states={
            'required': Bool(Eval('clearing_account')),
            },
        depends=['clearing_account'])
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
                        ]))
        Move.post(moves)


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'
    account = fields.Many2One(
        'account.account', "Account", ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['receivable', 'payable', 'deposit']),
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
        depends=['company', 'currency', 'state', 'line'],
        help="Define the account to use for clearing move.")
    clearing_move = fields.Many2One('account.move', 'Clearing Move',
        readonly=True)

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
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        super(Payment, cls).succeed(payments)

        moves = []
        for payment in payments:
            move = payment.create_clearing_move(
                date=Transaction().context.get('clearing_date'))
            if move:
                moves.append(move)
        if moves:
            Move.save(moves)
            cls.write(*sum((([m.origin], {'clearing_move': m.id})
                        for m in moves), ()))

        to_reconcile = []
        for payment in payments:
            if (payment.line
                    and not payment.line.reconciliation
                    and payment.clearing_move):
                lines = [l for l in payment.clearing_move.lines
                    if l.account == payment.line.account] + [payment.line]
                if not sum(l.debit - l.credit for l in lines):
                    to_reconcile.append(lines)
        for lines in to_reconcile:
            Line.reconcile(lines)

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

    def create_clearing_move(self, date=None):
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
    @Workflow.transition('failed')
    def fail(cls, payments):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')

        super(Payment, cls).fail(payments)

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

        # Remove clearing_move before delete in case reconciliation triggers
        # would use it.
        cls.write(payments, {'clearing_move': None})

        if to_unreconcile:
            Reconciliation.delete(to_unreconcile)
        if to_delete:
            Move.delete(to_delete)
        for party in to_reconcile:
            for lines in to_reconcile[party].values():
                Line.reconcile(lines)

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('clearing_move')
        return super(Payment, cls).copy(payments, default=default)


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
        pool = Pool()
        Payment = pool.get('account.payment')
        payments = Payment.browse(Transaction().context['active_ids'])

        with Transaction().set_context(clearing_date=self.start.date):
            Payment.succeed(payments)
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
