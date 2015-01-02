# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['Purchase', 'PurchaseLine', 'AnalyticAccountEntry']
__metaclass__ = PoolMeta


class Purchase:
    __name__ = "purchase.purchase"

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'analytic_account_required': ('Analytic account is required '
                    'on line "%s".'),
                })

    def check_for_quotation(self):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        super(Purchase, self).check_for_quotation()

        for line in self.lines:
            if line.type != 'line':
                continue
            if not AnalyticAccountEntry.check_root(line.analytic_accounts):
                self.raise_user_error('analytic_account_required',
                    line.rec_name)


class PurchaseLine(AnalyticMixin):
    __name__ = 'purchase.line'

    def get_invoice_line(self, invoice_type):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        invoice_lines = super(PurchaseLine, self).get_invoice_line(
            invoice_type)
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
        return origins + ['purchase.line']
