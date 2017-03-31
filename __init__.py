# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from stock import *
from production import *
from product import *


def register():
    Pool.register(
        OrderPoint,
        LocationLeadTime,
        Configuration,
        ConfigurationSupplyPeriod,
        Production,
        Product,
        module='stock_supply_production', type_='model')
    Pool.register(
        StockSupply,
        module='stock_supply_production', type_='wizard')
