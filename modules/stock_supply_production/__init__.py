# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import production
from . import product


def register():
    Pool.register(
        stock.OrderPoint,
        stock.LocationLeadTime,
        production.Configuration,
        production.ConfigurationSupplyPeriod,
        production.Production,
        product.Product,
        module='stock_supply_production', type_='model')
    Pool.register(
        stock.StockSupply,
        module='stock_supply_production', type_='wizard')
