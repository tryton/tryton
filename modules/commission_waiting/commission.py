# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, fields
from trytond.pyson import Eval, Bool


__all__ = ['Agent', 'Commission']


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'
    waiting_account = fields.Many2One('account.account', 'Waiting Account',
        domain=[
            ('company', '=', Eval('company')),
            ('kind', 'in', ['payable', 'other']),
            ],
        depends=['company'])


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'
    waiting_move = fields.Many2One('account.move', 'Move', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.states['readonly'] |= Bool(Eval('waiting_move'))
        cls.amount.depends.append('waiting_move')

    @classmethod
    def copy(cls, commissions, default=None):
        if default is None:
            default = {}
        default.setdefault('waiting_move', None)
        return super(Commission, cls).copy(commissions, default=default)

    @classmethod
    @ModelView.button
    def create_waiting_move(cls, commissions):
        pool = Pool()
        Move = pool.get('account.move')
        Commission = pool.get('commission')
        moves = []
        for commission in commissions:
            move = commission.get_move()
            if move:
                moves.append(move)
            commission.waiting_move = move

        Move.save(moves)
        Commission.save(commissions)

    def get_move(self, date=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Currency = pool.get('currency.currency')

        if not self.agent.waiting_account:
            return
        if self.waiting_move:
            return self.waiting_move

        if date is None:
            date = Date.today()
        period = Period.find(self.agent.company.id, date=date)

        move = Move(journal=self.get_journal(), origin=self,
            date=date, period=period)
        amount = Currency.compute(self.currency, self.amount,
            self.agent.company.currency)
        line = Line()
        if self.type_ == 'in':
            line.credit = amount if amount > 0 else 0
            line.debit = amount if amount < 0 else 0
            line.account = self.product.account_revenue_used
        else:
            line.debit = amount if amount > 0 else 0
            line.credit = amount if amount < 0 else 0
            line.account = self.product.account_expense_used
        if line.account.party_required:
            line.party = self.agent.party
        # XXX second currency?
        counterpart = Line()
        counterpart.debit, counterpart.credit = line.credit, line.debit
        counterpart.account = self.agent.waiting_account
        if counterpart.account.party_required:
            counterpart.party = self.agent.party
        move.lines = (line, counterpart)
        return move
