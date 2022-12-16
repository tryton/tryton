#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from stock import *
from production import *
from product import *


def register():
    Pool.register(
        OrderPoint,
        Configuration,
        Production,
        CreateProductionRequestStart,
        Product,
        module='stock_supply_production', type_='model')
    Pool.register(
        CreateProductionRequest,
        module='stock_supply_production', type_='wizard')
