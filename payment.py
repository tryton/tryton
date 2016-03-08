# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval, Bool

__all__ = ['Journal', 'Payment']


class Journal:
    __metaclass__ = PoolMeta
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


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'
    clearing_move = fields.Many2One('account.move', 'Clearing Move',
        readonly=True)

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
            move = payment.create_clearing_move()
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

    def create_clearing_move(self, date=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        if not self.line:
            return
        if (not self.journal.clearing_account
                or not self.journal.clearing_journal):
            return
        if self.clearing_move:
            return self.clearing_move

        if date is None:
            date = Date.today()
        period = Period.find(self.company.id, date=date)

        move = Move(journal=self.journal.clearing_journal, origin=self,
            date=date, period=period)
        line = Line()
        if self.kind == 'payable':
            line.debit, line.credit = self.amount, 0
        else:
            line.debit, line.credit = 0, self.amount
        line.account = self.line.account
        line.amount_second_currency = (-self.line.amount_second_currency
            if self.line.amount_second_currency else None)
        line.second_currency = self.line.second_currency
        line.party = (self.line.party
            if self.line.account.party_required else None)
        counterpart = Line()
        if self.kind == 'payable':
            counterpart.debit, counterpart.credit = 0, self.amount
        else:
            counterpart.debit, counterpart.credit = self.amount, 0
        counterpart.account = self.journal.clearing_account
        counterpart.amount_second_currency = self.line.amount_second_currency
        counterpart.second_currency = self.line.second_currency
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
        if to_unreconcile:
            Reconciliation.delete(to_unreconcile)
        if to_delete:
            Move.delete(to_delete)
        for party in to_reconcile:
            for lines in to_reconcile[party].itervalues():
                Line.reconcile(lines)

        cls.write(payments, {'clearing_move': None})
