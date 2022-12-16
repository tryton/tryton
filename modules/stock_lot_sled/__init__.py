# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .product import *
from .stock import *


def register():
    Pool.register(
        Template,
        Product,
        Configuration,
        Lot,
        Move,
        Period,
        module='stock_lot_sled', type_='model')
