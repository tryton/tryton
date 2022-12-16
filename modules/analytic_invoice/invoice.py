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

        result = super(InvoiceLine, self)._credit()
        if self.analytic_accounts:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            result['analytic_accounts'] = [('add',
                    [e.id for e in new_entries])]

        return result

    def get_analytic_entry(self, entry, value):
        analytic_entry = {}
        analytic_entry['name'] = self.description
        analytic_entry['debit'] = value['debit']
        analytic_entry['credit'] = value['credit']
        analytic_entry['account'] = entry.account.id
        analytic_entry['journal'] = self.invoice.journal.id
        analytic_entry['date'] = (self.invoice.accounting_date or
            self.invoice.invoice_date)
        analytic_entry['reference'] = self.invoice.reference
        analytic_entry['party'] = self.invoice.party.id
        return analytic_entry

    def get_move_line(self):
        values = super(InvoiceLine, self).get_move_line()
        if self.analytic_accounts:
            for value in values:
                value['analytic_lines'] = []
                to_create = []
                for entry in self.analytic_accounts:
                    if not entry.account:
                        continue
                    to_create.append(self.get_analytic_entry(entry, value))
                if to_create:
                    value['analytic_lines'] = [('create', to_create)]
        return values


class AnalyticAccountEntry:
    __metaclass__ = PoolMeta
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['account.invoice.line']
