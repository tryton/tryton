# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import party, product, purchase, sale, stock


def register():
    Pool.register(
        stock.Configuration,
        stock.ConfigurationSequence,
        stock.ShipmentDrop,
        stock.Move,
        sale.Configuration,
        sale.ConfigurationSaleDropLocation,
        sale.Sale,
        sale.Line,
        purchase.Request,
        purchase.Configuration,
        purchase.ConfigurationPurchaseDropLocation,
        purchase.Purchase,
        purchase.Line,
        purchase.ProductSupplier,
        product.Product,
        module='sale_supply_drop_shipment', type_='model')
    Pool.register(
        purchase.RequestCreatePurchase,
        purchase.HandleShipmentException,
        party.Replace,
        party.Erase,
        module='sale_supply_drop_shipment', type_='wizard')
