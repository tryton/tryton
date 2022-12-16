# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, product, stock

__all__ = ['register']


def register():
    Pool.register(
        product.Template,
        product.Product,
        account.Configuration,
        account.ConfigurationShipmentCostSequence,
        account.ShipmentCost,
        account.ShipmentCost_Shipment,
        account.ShipmentCost_ShipmentReturn,
        account.InvoiceLine,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        module='account_stock_shipment_cost', type_='model')
    Pool.register(
        module='account_stock_shipment_cost', type_='wizard')
    Pool.register(
        module='account_stock_shipment_cost', type_='report')
