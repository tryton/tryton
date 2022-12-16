# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta


def _percentage_amount(lines, company):
    pool = Pool()
    Move = pool.get('stock.move')
    Currency = pool.get('currency.currency')

    amount = 0
    for line in lines or []:
        unit_price = getattr(line, 'unit_price', None)
        currency = getattr(line, 'currency', None)
        if unit_price is None and isinstance(line.origin, Move):
            unit_price = line.origin.unit_price
            currency = line.origin.currency
        if unit_price is None:
            unit_price = Decimal(0)
            currency = None
        if currency:
            unit_price = Currency.compute(currency, unit_price,
                company.currency, round=False)
        amount += unit_price * Decimal(str(line.quantity or 0))
    return amount


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @fields.depends('carrier', 'incoming_moves', 'company')
    def _get_carrier_context(self):
        context = super(ShipmentIn, self)._get_carrier_context()
        if not self.carrier or not self.company:
            return context
        if self.carrier.carrier_cost_method != 'percentage':
            return context
        context['amount'] = _percentage_amount(
            self.incoming_moves, self.company)
        context['currency'] = self.company.currency.id
        return context


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @fields.depends('carrier', 'inventory_moves', 'company')
    def _get_carrier_context(self):
        context = super(ShipmentOut, self)._get_carrier_context()
        if not self.carrier or not self.company:
            return context
        if self.carrier.carrier_cost_method != 'percentage':
            return context
        context['amount'] = _percentage_amount(
            self.inventory_moves, self.company)
        context['currency'] = self.company.currency.id
        return context
