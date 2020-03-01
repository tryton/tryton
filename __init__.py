# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import product
from . import move


def register():
    Pool.register(
        product.Template,
        product.Product,
        move.Move,
        module='product_cost_fifo', type_='model')
