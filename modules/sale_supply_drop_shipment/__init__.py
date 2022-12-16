# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from stock import *
from sale import *
from purchase import *


def register():
    Pool.register(
        Configuration,
        ShipmentDrop,
        Move,
        SaleConfig,
        Sale,
        SaleLine,
        PurchaseRequest,
        PurchaseConfig,
        Purchase,
        PurchaseLine,
        ProductSupplier,
        module='sale_supply_drop_shipment', type_='model')
    Pool.register(
        CreatePurchase,
        PurchaseHandleShipmentException,
        module='sale_supply_drop_shipment', type_='wizard')
