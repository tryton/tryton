# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow


__all__ = ['Invoice', 'InvoiceLine']


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        cls.post_commission_waiting_moves(invoices)

    @classmethod
    def create_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')

        commissions = super(Invoice, cls).create_commissions(invoices)

        Commission.create_waiting_move(commissions)
        return commissions

    @classmethod
    def post_commission_waiting_moves(cls, invoices):
        pool = Pool()
        Move = pool.get('account.move')

        moves = []
        for invoice in invoices:
            for line in invoice.lines:
                for commission in line.from_commissions:
                    if (commission.waiting_move
                            and commission.waiting_move.state != 'posted'):
                        moves.append(commission.waiting_move)
        if moves:
            Move.post(moves)


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'

    def get_move_line(self):
        lines = super(InvoiceLine, self).get_move_line()
        if self.from_commissions:
            amounts = defaultdict(lambda: 0)
            for commission in self.from_commissions:
                if not commission.waiting_move:
                    continue
                for line in commission.waiting_move.lines:
                    amounts[(line.account, line.party)] += (
                        line.debit - line.credit)
            for (account, party), amount in amounts.iteritems():
                lines.append({
                        'debit': -amount if amount < 0 else 0,
                        'credit': amount if amount > 0 else 0,
                        'account': account.id,
                        'party': party.id if party else None,
                        'amount_second_currency': None,
                        })
        return lines
