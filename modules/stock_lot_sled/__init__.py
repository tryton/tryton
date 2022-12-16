# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import stock


def register():
    Pool.register(
        product.Template,
        product.Product,
        stock.Configuration,
        stock.ConfigurationLotShelfLife,
        stock.Lot,
        stock.Move,
        stock.Period,
        module='stock_lot_sled', type_='model')
