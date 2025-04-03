# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import groupby

from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def get_credit_amount(cls, parties, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Sale = pool.get('sale.sale')
        Uom = pool.get('product.uom')

        amounts = super().get_credit_amount(parties, name)

        company_id = Transaction().context.get('company')

        for sub_parties in grouped_slice(parties):
            id2party = {p.id: p for p in sub_parties}

            sales = Sale.search([
                    ('company', '=', company_id),
                    ('party', 'in', list(id2party.keys())),
                    ('state', 'in', ['confirmed', 'processing']),
                    ],
                order=[('party', None)])
            for party_id, sales in groupby(sales, lambda s: s.party.id):
                party = id2party[party_id]
                for sale in sales:
                    amount = 0
                    for line in sale.lines:
                        quantity = line.credit_limit_quantity
                        if quantity is None:
                            continue
                        for invoice_line in line.invoice_lines:
                            if invoice_line.type != 'line':
                                continue
                            invoice = invoice_line.invoice
                            if invoice and invoice.move:
                                if line.unit:
                                    quantity -= Uom.compute_qty(
                                        invoice_line.unit or line.unit,
                                        invoice_line.quantity,
                                        line.unit, round=False)
                                else:
                                    quantity -= invoice_line.quantity
                        if quantity > 0:
                            amount += Currency.compute(
                                sale.currency,
                                Decimal(str(quantity)) * line.unit_price,
                                party.currency,
                                round=False)
                    amounts[party.id] = party.currency.round(
                        amounts[sale.party.id] + amount)
        return amounts

    @classmethod
    def _credit_limit_to_lock(cls):
        return super()._credit_limit_to_lock() + [
            'sale.sale', 'sale.line']
