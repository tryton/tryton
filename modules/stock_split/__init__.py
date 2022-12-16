# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock


def register():
    Pool.register(
        stock.Move,
        stock.SplitMoveStart,
        stock.ShipmentInReturn,
        stock.ShipmentOut,
        stock.ShipmentInternal,
        stock.SplitShipmentStart,
        module='stock_split', type_='model')
    Pool.register(
        stock.SplitMove,
        stock.SplitShipment,
        module='stock_split', type_='wizard')
