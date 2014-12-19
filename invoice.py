# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals
from collections import defaultdict

from trytond.pool import PoolMeta, Pool


__all__ = ['Invoice', 'InvoiceLine']
__metaclass__ = PoolMeta


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def create_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')

        commissions = super(Invoice, cls).create_commissions(invoices)

        Commission.create_waiting_move(commissions)
        return commissions


class InvoiceLine:
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
