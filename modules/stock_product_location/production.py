# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @fields.depends('warehouse')
    def _move(self, type, product, unit, quantity):
        move = super()._move(type, product, unit, quantity)
        if move and type == 'output' and self.warehouse:
            move.set_product_location(warehouse=self.warehouse.id)
        return move
