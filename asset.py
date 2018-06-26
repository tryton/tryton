# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields

from trytond.modules.analytic_account import AnalyticMixin

__all__ = ['Asset']


class Asset(AnalyticMixin, metaclass=PoolMeta):
    __name__ = 'account.asset'

    @fields.depends('supplier_invoice_line', 'analytic_accounts')
    def on_change_supplier_invoice_line(self):
        pool = Pool()
        Entry = pool.get('analytic.account.entry')

        super(Asset, self).on_change_supplier_invoice_line()
        if self.supplier_invoice_line:
            entries = []
            for entry in self.supplier_invoice_line.analytic_accounts:
                new_entry = Entry()
                for field in Entry._fields:
                    if field in {'origin', 'id'}:
                        continue
                    setattr(new_entry, field, getattr(entry, field))
                entries.append(new_entry)
            self.analytic_accounts = entries

    def get_move(self, line):
        move = super(Asset, self).get_move(line)
        self.set_analytic_lines(move)
        return move

    def get_closing_move(self, account):
        move = super(Asset, self).get_closing_move(account)
        self.set_analytic_lines(move)
        return move

    def set_analytic_lines(self, move):
        "Fill analytic lines on lines with expense account"
        if self.analytic_accounts:
            for line in move.lines:
                if line.account != self.product.account_expense_used:
                    continue
                analytic_lines = []
                for entry in self.analytic_accounts:
                    analytic_lines.extend(
                        entry.get_analytic_lines(line, move.date))
                line.analytic_lines = analytic_lines
