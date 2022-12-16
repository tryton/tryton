#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['ShipmentIn', 'ShipmentOut']
__metaclass__ = PoolMeta


def _percentage_amount(lines, company):
    pool = Pool()
    Move = pool.get('stock.move')
    Currency = pool.get('currency.currency')

    amount = 0
    for line in lines or []:
        unit_price = getattr(line, 'unit_price',
            Move.default_unit_price() if hasattr(Move, 'default_unit_price')
            else Decimal(0))
        currency = getattr(line, 'currency',
            Move.default_currency() if hasattr(Move, 'default_currency')
            else None)
        if currency:
            unit_price = Currency.compute(currency, unit_price,
                company.currency, round=False)
        amount += unit_price * Decimal(str(line.quantity or 0))
    return amount


class ShipmentIn:
    __name__ = 'stock.shipment.in'

    def _get_carrier_context(self):
        Company = Pool().get('company.company')
        context = super(ShipmentIn, self)._get_carrier_context()
        if not self.carrier:
            return context
        context = context.copy()
        if self.carrier.carrier_cost_method != 'percentage':
            return context
        company = Company(Transaction().context['company'])
        context['amount'] = _percentage_amount(self.incoming_moves, company)
        context['currency'] = company.currency.id
        return context


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    def _get_carrier_context(self):
        Company = Pool().get('company.company')

        context = super(ShipmentOut, self)._get_carrier_context()
        if not self.carrier:
            return context
        context = context.copy()
        if self.carrier.carrier_cost_method != 'percentage':
            return context
        company = Company(Transaction().context['company'])
        context['amount'] = _percentage_amount(self.inventory_moves, company)
        context['currency'] = company.currency.id
        return context
