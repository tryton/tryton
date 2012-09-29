#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .stock import *
from .product import *
from .account import *


def register():
    Pool.register(
        Move,
        Category,
        Template,
        Configuration,
        AccountMove,
        UpdateCostPriceAsk,
        UpdateCostPriceShowMove,
        module='account_stock_continental', type_='model')
    Pool.register(
        UpdateCostPrice,
        module='account_stock_continental', type_='wizard')
