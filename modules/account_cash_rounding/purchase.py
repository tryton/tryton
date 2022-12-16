# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.account_invoice.exceptions import PaymentTermComputeError


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    cash_rounding = fields.Boolean(
        "Cash Rounding",
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    @fields.depends('party')
    def on_change_party(self):
        cursor = Transaction().connection.cursor()
        table = self.__table__()
        super().on_change_party()
        if self.party:
            cursor.execute(*table.select(table.cash_rounding,
                    where=table.party == self.party.id,
                    order_by=table.id,
                    limit=1))
            row = cursor.fetchone()
            if row:
                self.cash_rounding, = row

    @fields.depends(methods=['on_change_lines'])
    def on_change_cash_rounding(self):
        self.on_change_lines()

    @fields.depends('cash_rounding', methods=['_cash_round_total_amount'])
    def on_change_lines(self):
        super().on_change_lines()
        if self.cash_rounding:
            self.total_amount = self._cash_round_total_amount(
                self.total_amount)

    @classmethod
    def get_amount(cls, purchases, names):
        amounts = super().get_amount(purchases, names)
        if 'total_amount' in names:
            total_amounts = amounts['total_amount']
            for purchase in purchases:
                if purchase.cash_rounding:
                    amount = total_amounts[purchase.id]
                    amount = purchase._cash_round_total_amount(amount)
                    total_amounts[purchase.id] = amount
        return amounts

    @fields.depends('currency', 'payment_term', 'company')
    def _cash_round_total_amount(self, amount):
        if self.currency:
            amounts = [amount]
            if self.payment_term and self.company:
                try:
                    term_lines = self.payment_term.compute(
                        amount, self.company.currency)
                    amounts = [a for _, a in term_lines]
                except PaymentTermComputeError:
                    pass
            amount = sum(map(self.currency.cash_round, amounts))
        return amount

    def _get_invoice_purchase(self):
        invoice = super()._get_invoice_purchase()
        invoice.cash_rounding = self.cash_rounding
        return invoice
