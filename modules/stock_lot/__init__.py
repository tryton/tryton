# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, stock
from .stock import LotMixin

__all__ = ['LotMixin', 'register']


def register():
    Pool.register(
        stock.Lot,
        stock.LotTrace,
        stock.LotByLocationContext,
        stock.LotsByLocations,
        stock.LotByWarehouseContext,
        stock.Location,
        stock.Move,
        stock.MoveAddLotsStart,
        stock.MoveAddLotsStartLot,
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        stock.Period,
        stock.PeriodCacheLot,
        stock.Inventory,
        stock.InventoryLine,
        stock.InventoryCountSearch,
        product.Configuration,
        product.ConfigurationDefaultLotSequence,
        product.Template,
        product.Product,
        module='stock_lot', type_='model')
    Pool.register(
        stock.MoveAddLots,
        stock.InventoryCount,
        module='stock_lot', type_='wizard')
