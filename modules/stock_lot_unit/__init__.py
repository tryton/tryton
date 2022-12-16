# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import stock

__all__ = ['register']


def register():
    Pool.register(
        product.Template,
        product.Product,
        stock.Lot,
        stock.Move,
        stock.Inventory,
        stock.ShipmentIn,
        stock.ShipmentInReturn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        module='stock_lot_unit', type_='model')
    Pool.register(
        stock.Production,
        module='stock_lot_unit', type_='model',
        depends=['production'])
    Pool.register(
        stock.InventoryCount,
        module='stock_lot_unit', type_='wizard')
