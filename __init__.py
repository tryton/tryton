# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    ir, location, order_point, product, purchase_request, shipment, stock)


def register():
    Pool.register(
        order_point.OrderPoint,
        product.Product,
        product.ProductSupplier,
        purchase_request.PurchaseConfiguration,
        purchase_request.PurchaseConfigurationSupplyPeriod,
        purchase_request.PurchaseRequest,
        shipment.ShipmentInternal,
        location.Location,
        location.LocationLeadTime,
        stock.SupplyStart,
        ir.Cron,
        module='stock_supply', type_='model')
    Pool.register(
        stock.Supply,
        module='stock_supply', type_='wizard')
