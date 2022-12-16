# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['SaleLine', 'AnalyticAccountEntry']
__metaclass__ = PoolMeta


class SaleLine(AnalyticMixin):
    __name__ = 'sale.line'

    def get_invoice_line(self, invoice_type):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        invoice_lines = super(SaleLine, self).get_invoice_line(invoice_type)
        for invoice_line in invoice_lines:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            invoice_line.analytic_accounts = new_entries
        return invoice_lines


class AnalyticAccountEntry:
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['sale.line']
