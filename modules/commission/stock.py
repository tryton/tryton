# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import fields
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    commission_price = fields.Numeric(
        "Commission Price", digits=price_digits, readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period.add('commission_price')

    @classmethod
    def update_unit_price(cls, moves):
        for move in moves:
            if move.state == 'done':
                commission_price = move._compute_commission_price()
                if commission_price != move.commission_price:
                    move.commission_price = commission_price
        super().update_unit_price(moves)

    def _compute_commission_price(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        Currency = pool.get('currency.currency')
        total, quantity = 0, 0
        for line in self.invoice_lines:
            if line.invoice and line.invoice.state in {'posted', 'paid'}:
                for commission in line.commissions:
                    with Transaction().set_context(date=self.effective_date):
                        amount = Currency.compute(
                            commission.currency, commission.amount,
                            self.currency)
                        if line.invoice.type == commission.type_:
                            total -= amount
                        else:
                            total += amount
                if line.invoice.type == 'out' or not line.correction:
                    quantity += UoM.compute_qty(
                        line.unit, line.quantity, self.unit)
        if quantity:
            unit_price = round_price(total / Decimal(str(quantity)))
        else:
            unit_price = round_price(total)
        return unit_price
