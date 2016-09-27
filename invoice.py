# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['InvoiceLine', 'AnalyticAccountEntry']


class InvoiceLine(AnalyticMixin):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.analytic_accounts.domain = [
            ('company', '=', If(~Eval('company'),
                    Eval('context', {}).get('company', -1),
                    Eval('company', -1))),
            ]
        cls.analytic_accounts.depends.append('company')

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

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if isinstance(self.origin, InvoiceLine):
            company = self.origin.company.id
        return company

    @classmethod
    def search_company(cls, name, clause):
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause),
        return ['OR',
            domain,
            (('origin.company',) + tuple(clause[1:]) +
                ('account.invoice.line',)),
            ]
