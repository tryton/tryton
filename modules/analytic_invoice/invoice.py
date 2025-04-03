# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.analytic_account import AnalyticMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class InvoiceLine(AnalyticMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.analytic_accounts.domain = [
            ('company', '=', Eval('company', -1)),
            ]
        cls.analytic_accounts.states = {
            'invisible': Eval('type') != 'line',
            'readonly': Eval('invoice_state') != 'draft',
            }

    def _credit(self):
        pool = Pool()
        AnalyticAccountEntry = pool.get('analytic.account.entry')

        line = super()._credit()
        if self.analytic_accounts:
            new_entries = AnalyticAccountEntry.copy(self.analytic_accounts,
                default={
                    'origin': None,
                    })
            line.analytic_accounts = new_entries
        return line

    def get_move_lines(self):
        lines = super().get_move_lines()
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


class InvoiceDeferred(metaclass=PoolMeta):
    __name__ = 'account.invoice.deferred'

    def get_move(self, period=None):
        move = super().get_move(period=period)
        if self.invoice_line.analytic_accounts:
            for line in move.lines:
                if line.account.type.statement != 'income':
                    continue
                analytic_lines = []
                for entry in self.invoice_line.analytic_accounts:
                    analytic_lines.extend(
                        entry.get_analytic_lines(line, move.date))
                line.analytic_lines = analytic_lines
        return move


class AnalyticAccountEntry(metaclass=PoolMeta):
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        pool = Pool()
        origins = super()._get_origin()
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
        company = super().on_change_with_company(name=name)
        if (isinstance(self.origin, InvoiceLine)
                or (Asset and isinstance(self.origin, Asset))):
            company = self.origin.company
        return company

    @classmethod
    def search_company(cls, name, clause):
        pool = Pool()
        domain = super().search_company(name, clause),
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

    @fields.depends('origin')
    def on_change_with_editable(self, name=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        try:
            Asset = pool.get('account.asset')
        except KeyError:
            Asset = None

        editable = super().on_change_with_editable(name=name)

        if isinstance(self.origin, InvoiceLine):
            if self.origin.invoice_state != 'draft':
                editable = False
        elif Asset and isinstance(self.origin, Asset):
            if self.origin.state != 'draft':
                editable = False
        return editable
