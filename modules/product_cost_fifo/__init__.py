# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .product import *
from .move import *


def register():
    Pool.register(
        Template,
        Product,
        Move,
        module='product_cost_fifo', type_='model')
