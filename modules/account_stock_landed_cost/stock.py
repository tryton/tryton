# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.product import price_digits
from trytond.pool import PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    unit_landed_cost = fields.Numeric('Unit Landed Cost',
        digits=price_digits, readonly=True)

    def _compute_unit_price(self, unit_price):
        if self.unit_landed_cost:
            unit_price -= self.unit_landed_cost
        unit_price = super()._compute_unit_price(unit_price)
        if self.unit_landed_cost:
            unit_price += self.unit_landed_cost
        return unit_price

    def _compute_component_unit_price(self, unit_price):
        if self.unit_landed_cost:
            unit_price -= self.unit_landed_cost
        unit_price = super()._compute_component_unit_price(unit_price)
        if self.unit_landed_cost:
            unit_price += self.unit_landed_cost
        return unit_price
