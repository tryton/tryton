# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, purchase, sale, stock


def register():
    Pool.register(
        sale.Sale,
        sale.Line,
        purchase.Request,
        stock.ShipmentIn,
        product.Template,
        product.Product,
        module='sale_supply', type_='model')
    Pool.register(
        stock.OrderPoint,
        module='sale_supply', type_='model', depends=['stock_supply'])
