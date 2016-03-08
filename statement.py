# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

__all__ = ['Statement', 'StatementLine']


class Statement:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement'

    @classmethod
    def create_move(cls, statements):
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        moves = super(Statement, cls).create_move(statements)

        for move, statement, lines in moves:
            assert len({l.payment for l in lines}) == 1
            line = lines[0]
            if line.payment and line.payment.clearing_move:
                clearing_account = line.payment.journal.clearing_account
                if clearing_account.reconcile:
                    to_reconcile = []
                    for line in move.lines + line.payment.clearing_move.lines:
                        if (line.account == clearing_account
                                and not line.reconciliation):
                            to_reconcile.append(line)
                    if not sum((l.debit - l.credit) for l in to_reconcile):
                        MoveLine.reconcile(to_reconcile)
        return moves

    def _group_key(self, line):
        key = super(Statement, self)._group_key(line)
        return key + (('payment', line.payment),)


class StatementLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line'
    payment = fields.Many2One('account.payment', 'Payment',
        domain=[
            If(Bool(Eval('party')), [('party', '=', Eval('party'))], []),
            ('state', 'in', ['processing', 'succeeded']),
            ],
        depends=['party'])

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default.setdefault('payment', None)
        return super(StatementLine, cls).copy(lines, default=default)

    @fields.depends('payment', 'party', 'account', '_parent_statement.journal')
    def on_change_payment(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        if self.payment:
            if not self.party:
                self.party = self.payment.party
            clearing_account = self.payment.journal.clearing_account
            if (not self.account
                    and self.payment.clearing_move
                    and clearing_account):
                self.account = clearing_account
            if self.statement and self.statement.journal:
                with Transaction().set_context(date=self.payment.date):
                    amount = Currency.compute(self.payment.currency,
                        self.payment.amount, self.statement.journal.currency)
                self.amount = amount
                if self.payment.kind == 'payable':
                    self.amount *= -1

    @fields.depends('party', 'payment')
    def on_change_party(self):
        super(StatementLine, self).on_change_party()
        if self.payment:
            if self.payment.party != self.party:
                self.payment = None

    @fields.depends('account', 'payment')
    def on_change_account(self):
        super(StatementLine, self).on_change_account()
        if self.payment:
            clearing_account = self.payment.journal.clearing_account
            if self.account != clearing_account:
                self.payment = None

    @classmethod
    def post_move(cls, lines):
        pool = Pool()
        Move = pool.get('account.move')
        super(StatementLine, cls).post_move(lines)
        Move.post([l.payment.clearing_move for l in lines
                if l.payment and l.payment.clearing_move])
