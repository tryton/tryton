# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale
from . import purchase
from . import stock
from . import product


def register():
    Pool.register(
        sale.Sale,
        sale.Line,
        purchase.Request,
        purchase.Purchase,
        stock.ShipmentIn,
        product.Template,
        product.Product,
        module='sale_supply', type_='model')
    Pool.register(
        purchase.HandlePurchaseCancellationException,
        module='sale_supply', type_='wizard')
