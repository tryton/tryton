# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.modules.product import price_digits


__all__ = ['Move']


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    unit_landed_cost = fields.Numeric('Unit Landed Cost',
        digits=price_digits, readonly=True)
