# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    non_deductible = fields.Boolean(
        "Non-Deductible",
        help="Check to always include the tax amount as expense.")

    @classmethod
    def default_non_deductible(cls):
        return False

    def _get_tax_value(self, tax=None):
        value = super()._get_tax_value(tax=tax)
        if not tax or tax.non_deductible != self.non_deductible:
            value['non_deductible'] = self.non_deductible
        return value


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    non_deductible = fields.Boolean("Non-Deductible")

    @classmethod
    def default_non_deductible(cls):
        return False


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends(
        'type', 'invoice', '_parent_invoice.type', methods=['_get_taxes'])
    def on_change_with_amount(self):
        amount = super().on_change_with_amount()
        if self.type == 'line':
            invoice_type = (
                self.invoice.type if self.invoice else self.invoice_type)
            if invoice_type == 'in':
                with Transaction().set_context(
                        _non_deductible=True, _deductible_rate=1):
                    tax_amount = sum(
                        t['amount'] for t in self._get_taxes().values())
                amount += tax_amount
        return amount

    @property
    def taxable_lines(self):
        context = Transaction().context
        lines = super().taxable_lines
        if (getattr(self, 'invoice', None)
                and getattr(self.invoice, 'type', None)):
            invoice_type = self.invoice.type
        else:
            invoice_type = getattr(self, 'invoice_type', None)
        if invoice_type == 'in':
            if context.get('_non_deductible'):
                for line in lines:
                    taxes = line[0]
                    for tax in list(taxes):
                        if not tax.non_deductible:
                            taxes.remove(tax)
            else:
                for line in lines:
                    taxes = line[0]
                    for tax in list(taxes):
                        if tax.non_deductible:
                            taxes.remove(tax)
        return lines

    def _compute_taxes(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        TaxLine = pool.get('account.tax.line')

        tax_lines = super()._compute_taxes()
        with Transaction().set_context(
                _non_deductible=True, _deductible_rate=1):
            taxes = self._get_taxes().values()
            for tax in taxes:
                for type_, amount in [('base', 'base'), ('tax', 'amount')]:
                    amount = tax[amount]
                    with Transaction().set_context(
                            date=self.invoice.currency_date):
                        amount = Currency.compute(
                            self.invoice.currency, amount,
                            self.invoice.company.currency)
                    tax_line = TaxLine()
                    tax_line.amount = amount
                    tax_line.type = type_
                    tax_line.tax = tax['tax']
                    tax_lines.append(tax_line)
        return tax_lines
