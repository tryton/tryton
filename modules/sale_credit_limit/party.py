# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'

    @classmethod
    def get_credit_amount(cls, parties, name):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Currency = pool.get('currency.currency')
        User = pool.get('res.user')

        amounts = super(Party, cls).get_credit_amount(parties, name)

        user = User(Transaction().user)
        if not user.company:
            return amounts
        currency = user.company.currency

        sales = Sale.search([
                ('party', 'in', [p.id for p in parties]),
                ('state', '=', 'processing'),
                ])
        for sale in sales:
            amount = 0
            for line in sale.lines:
                amount += Currency.compute(sale.currency, line.amount,
                    currency, round=False)
                for invoice_line in line.invoice_lines:
                    invoice = invoice_line.invoice
                    if invoice and invoice.move:
                        amount -= Currency.compute(invoice.currency,
                            invoice_line.amount, currency)
            amounts[sale.party.id] += amount
        return amounts

    @classmethod
    def _credit_limit_to_lock(cls):
        return super(Party, cls)._credit_limit_to_lock() + [
            'sale.sale', 'sale.line']
