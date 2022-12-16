# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .stock import *
from .product import *


def register():
    Pool.register(
        Lot,
        LotType,
        Move,
        ShipmentIn,
        ShipmentOut,
        ShipmentOutReturn,
        Period,
        PeriodCacheLot,
        Inventory,
        InventoryLine,
        Template,
        Product,
        TemplateLotType,
        module='stock_lot', type_='model')
