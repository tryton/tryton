# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import product

__all__ = ['register']


def register():
    Pool.register(
        stock.Location,
        stock.ShipmentInternal,
        stock.ShipmentInternal_Location,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        product.Product,
        module='stock_location_move', type_='model')
    Pool.register(
        stock.Supply,
        module='stock_location_move', type_='wizard',
        depends=['stock_supply'])
    Pool.register(
        module='stock_location_move', type_='report')
