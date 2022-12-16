# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, stock
from .stock import LotUnitMixin

__all__ = ['LotUnitMixin', 'register']


def register():
    Pool.register(
        product.Template,
        product.Product,
        stock.Lot,
        stock.MoveAddLotsStartLot,
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
