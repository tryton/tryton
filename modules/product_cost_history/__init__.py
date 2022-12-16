# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product

__all__ = ['register']


def register():
    Pool.register(
        product.Product,
        product.CostPrice,
        product.ProductCostHistory,
        module='product_cost_history', type_='model')
