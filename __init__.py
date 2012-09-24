#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .ir import *
from .product import *


def register():
    Pool.register(
        Property,
        ProductCostHistory,
        module='product_cost_history', type_='model')
    Pool.register(
        OpenProductCostHistory,
        module='product_cost_history', type_='wizard')
