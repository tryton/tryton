# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def must_check_credit_limit(self):
        return self.shipment_method == 'order'

    @property
    def credit_limit_amount(self):
        "Amount to check against credit limit"
        pool = Pool()
        Currency = pool.get('currency.currency')
        return Currency.compute(
            self.currency, self.untaxed_amount, self.company.currency)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        for sale in sales:
            if sale.must_check_credit_limit():
                party = sale.invoice_party or sale.party
                party.check_credit_limit(
                    sale.credit_limit_amount, sale.company, origin=sale)
        super().confirm(sales)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @property
    def credit_limit_quantity(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        if (self.type != 'line') or (self.quantity <= 0):
            return None
        quantity = self.quantity
        if self.sale.invoice_method == 'shipment':
            for move in self.moves_ignored:
                quantity -= UoM.compute_qty(
                    move.unit, move.quantity, self.unit, round=False)
        for invoice_line in self.invoice_lines:
            if invoice_line.invoice in self.sale.invoices_ignored:
                quantity -= UoM.compute_qty(
                    invoice_line.unit, invoice_line.quantity, self.unit,
                    round=False)
        return quantity
