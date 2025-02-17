# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, stock

__all__ = ['register']


def register():
    Pool.register(
        stock.ProductLocationPlace,
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentInReturn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        stock.InventoryLine,
        product.Template,
        product.Product,
        module='stock_product_location_place', type_='model')
