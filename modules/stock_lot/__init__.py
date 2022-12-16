# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import product


def register():
    Pool.register(
        stock.Lot,
        stock.LotByLocationContext,
        stock.LotType,
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.Period,
        stock.PeriodCacheLot,
        stock.Inventory,
        stock.InventoryLine,
        stock.InventoryCountSearch,
        product.Template,
        product.Product,
        product.TemplateLotType,
        module='stock_lot', type_='model')
    Pool.register(
        stock.InventoryCount,
        module='stock_lot', type_='wizard')
