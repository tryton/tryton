# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.analytic_account import AnalyticMixin


class InvoiceLine(AnalyticMixin, metaclass=PoolMeta):
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
        cls.analytic_accounts.states = {
            'invisible': Eval('type') != 'line',
            'readonly': Eval('invoice_state') != 'draft',
            }
        cls.analytic_accounts.depends.extend(['type', 'invoice_state'])

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

    def get_move_lines(self):
        lines = super(InvoiceLine, self).get_move_lines()
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type
        asset_depreciable = (self.product and type_ == 'in'
            and self.product.type == 'assets'
            and getattr(self.product, 'depreciable', False))
        if self.analytic_accounts and not asset_depreciable:
            date = self.invoice.accounting_date or self.invoice.invoice_date
            for line in lines:
                analytic_lines = []
                for entry in self.analytic_accounts:
                    analytic_lines.extend(
                        entry.get_analytic_lines(line, date))
                line.analytic_lines = analytic_lines
        return lines


class AnalyticAccountEntry(metaclass=PoolMeta):
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        pool = Pool()
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        origins.append('account.invoice.line')
        try:
            pool.get('account.asset')
            origins.append('account.asset')
        except KeyError:
            pass
        return origins

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        try:
            Asset = pool.get('account.asset')
        except KeyError:
            Asset = None
        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if (isinstance(self.origin, InvoiceLine)
                or (Asset and isinstance(self.origin, Asset))):
            company = self.origin.company.id if self.origin.company else None
        return company

    @classmethod
    def search_company(cls, name, clause):
        pool = Pool()
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause),
        domain = ['OR',
            domain,
            (('origin.' + clause[0],) + tuple(clause[1:3])
                + ('account.invoice.line',) + tuple(clause[3:])),
            ]
        try:
            pool.get('account.asset')
            domain.append(
                (('origin.' + clause[0],) + tuple(clause[1:3])
                    + ('account.asset',) + tuple(clause[3:])))
        except KeyError:
            pass
        return domain
