# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .product import *
from .account import *
from .stock import *


def register():
    Pool.register(
        Template,
        Product,
        Configuration,
        ConfigurationLandedCostSequence,
        LandedCost,
        LandedCost_Shipment,
        InvoiceLine,
        Move,
        module='account_stock_landed_cost', type_='model')
