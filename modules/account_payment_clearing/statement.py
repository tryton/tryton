# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

__all__ = ['StatementLine']
__metaclass__ = PoolMeta


class StatementLine:
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

    def create_move(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        move = super(StatementLine, self).create_move()
        if self.payment and self.payment.clearing_move:
            clearing_account = self.payment.journal.clearing_account
            if clearing_account.reconcile:
                to_reconcile = []
                for line in move.lines + self.payment.clearing_move.lines:
                    if (line.account == clearing_account
                            and not line.reconciliation):
                        to_reconcile.append(line)
                if not sum((l.debit - l.credit) for l in to_reconcile):
                    MoveLine.reconcile(to_reconcile)
        return move

    @fields.depends('payment', 'party', 'account', '_parent_statement.journal')
    def on_change_payment(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        changes = {}
        if self.payment:
            if not self.party:
                changes['party'] = self.payment.party.id
                changes['party.rec_name'] = self.payment.party.rec_name
            clearing_account = self.payment.journal.clearing_account
            if (not self.account
                    and self.payment.clearing_move
                    and clearing_account):
                changes['account'] = clearing_account.id
                changes['account.rec_name'] = clearing_account.rec_name
            if self.statement and self.statement.journal:
                with Transaction().set_context(date=self.payment.date):
                    amount = Currency.compute(self.payment.currency,
                        self.payment.amount, self.statement.journal.currency)
                changes['amount'] = amount
                if self.payment.kind == 'payable':
                    changes['amount'] *= -1
        return changes

    @fields.depends('party', 'payment')
    def on_change_party(self):
        changes = super(StatementLine, self).on_change_party()
        if self.payment:
            if self.payment.party != self.party:
                changes['payment'] = None
        return changes

    @fields.depends('account', 'payment')
    def on_change_account(self):
        changes = super(StatementLine, self).on_change_account()
        if self.payment:
            clearing_account = self.payment.journal.clearing_account
            if self.account != clearing_account:
                changes['payment'] = None
        return changes

    @classmethod
    def post_move(cls, lines):
        pool = Pool()
        Move = pool.get('account.move')
        super(StatementLine, cls).post_move(lines)
        Move.post([l.payment.clearing_move for l in lines
                if l.payment and l.payment.clearing_move])
