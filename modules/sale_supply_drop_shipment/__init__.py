# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import sale
from . import purchase
from . import party


def register():
    Pool.register(
        stock.Configuration,
        stock.ConfigurationSequence,
        stock.ShipmentDrop,
        stock.Move,
        sale.SaleConfig,
        sale.SaleConfigSaleDropLocation,
        sale.Sale,
        sale.SaleLine,
        purchase.PurchaseRequest,
        purchase.PurchaseConfig,
        purchase.PurchaseConfigPurchaseDropLocation,
        purchase.Purchase,
        purchase.PurchaseLine,
        purchase.ProductSupplier,
        module='sale_supply_drop_shipment', type_='model')
    Pool.register(
        purchase.CreatePurchase,
        purchase.PurchaseHandleShipmentException,
        party.PartyReplace,
        party.PartyErase,
        module='sale_supply_drop_shipment', type_='wizard')
