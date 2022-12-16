# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['Purchase', 'PurchaseLine', 'AnalyticAccountEntry']


class Purchase:
    __metaclass__ = PoolMeta
    __name__ = "purchase.purchase"

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'analytic_account_required': ('Analytic account is required '
                    'for "%(roots)s" on line "%(line)s".'),
                })

    def check_for_quotation(self):
        pool = Pool()
        Account = pool.get('analytic_account.account')
        mandatory_roots = {a for a in Account.search([
                ('type', '=', 'root'),
                ('mandatory', '=', True),
                ])}

        super(Purchase, self).check_for_quotation()

        for line in self.lines:
            if line.type != 'line':
                continue
            analytic_roots = {e.root for e in line.analytic_accounts
                if e.account}
            if not mandatory_roots <= analytic_roots:
                self.raise_user_error('analytic_account_required', {
                        'line': line.rec_name,
                        'roots': ', '.join(x.rec_name
                            for x in mandatory_roots - analytic_roots),
                        })


class PurchaseLine(AnalyticMixin):
    __metaclass__ = PoolMeta
    __name__ = 'purchase.line'

    @classmethod
    def __setup__(cls):
        super(PurchaseLine, cls).__setup__()
        cls.analytic_accounts.domain = [
            ('company', '=', If(~Eval('_parent_purchase'),
                    Eval('context', {}).get('company', -1),
                    Eval('_parent_purchase', {}).get('company', -1))),
            ]
        cls.analytic_accounts.states = {
            'invisible': Eval('type') != 'line',
            'readonly': Eval('purchase_state') != 'draft',
            }
        cls.analytic_accounts.depends.extend(['type', 'purchase_state'])

    def get_invoice_line(self):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        invoice_lines = super(PurchaseLine, self).get_invoice_line()
        for invoice_line in invoice_lines:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            invoice_line.analytic_accounts = new_entries
        return invoice_lines


class AnalyticAccountEntry:
    __metaclass__ = PoolMeta
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['purchase.line']

    @fields.depends('origin')
    def on_change_with_required(self, name=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        required = super(AnalyticAccountEntry, self).on_change_with_required(
            name)
        if (self.origin and isinstance(self.origin, PurchaseLine)
                and self.origin.purchase.state in ['cancel', 'draft']):
            return False
        return required

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if isinstance(self.origin, PurchaseLine) and self.origin.purchase:
            company = self.origin.purchase.company.id
        return company

    @classmethod
    def search_company(cls, name, clause):
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause)
        return ['OR',
            domain,
            (('origin.purchase.' + clause[0],) + tuple(clause[1:3])
                + ('purchase.line',) + tuple(clause[3:])),
            ]
