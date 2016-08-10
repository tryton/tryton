# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['InvoiceLine', 'AnalyticAccountEntry']


class InvoiceLine(AnalyticMixin):
    __name__ = 'account.invoice.line'

    def _credit(self):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        line = super(InvoiceLine, self)._credit()
        if self.analytic_accounts:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            line.analytic_accounts = new_entries
        return line

    def get_analytic_entry(self, entry, line):
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')

        analytic_line = AnalyticLine()
        analytic_line.name = self.description
        analytic_line.debit = line.debit
        analytic_line.credit = line.credit
        analytic_line.account = entry.account
        analytic_line.journal = self.invoice.journal
        analytic_line.date = (self.invoice.accounting_date
            or self.invoice.invoice_date)
        analytic_line.reference = self.invoice.reference
        analytic_line.party = self.invoice.party
        return analytic_line

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if self.analytic_accounts:
            for line in lines:
                analytic_lines = []
                for entry in self.analytic_accounts:
                    if not entry.account:
                        continue
                    analytic_lines.append(self.get_analytic_entry(entry, line))
                line.analytic_lines = analytic_lines
        return lines


class AnalyticAccountEntry:
    __metaclass__ = PoolMeta
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['account.invoice.line']
