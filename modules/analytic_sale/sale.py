# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['SaleLine', 'AnalyticAccountEntry']


class SaleLine(AnalyticMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.analytic_accounts.domain = [
            ('company', '=', If(~Eval('_parent_sale', {}),
                    Eval('context', {}).get('company', -1),
                    Eval('_parent_sale', {}).get('company', -1))),
            ]
        cls.analytic_accounts.states = {
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            }
        cls.analytic_accounts.depends.extend(['type', 'sale_state'])

    def get_invoice_line(self):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        invoice_lines = super(SaleLine, self).get_invoice_line()
        for invoice_line in invoice_lines:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            invoice_line.analytic_accounts = new_entries
        return invoice_lines


class AnalyticAccountEntry(metaclass=PoolMeta):
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['sale.line']

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if isinstance(self.origin, SaleLine) and self.origin.sale:
            company = self.origin.sale.company.id
        return company

    @classmethod
    def search_company(cls, name, clause):
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause),
        return ['OR',
            domain,
            (('origin.sale.' + clause[0],) + tuple(clause[1:3])
                + ('sale.line',) + tuple(clause[3:])),
            ]
