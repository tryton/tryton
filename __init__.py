# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .inventory import *


def register():
    Pool.register(
        CreateInventoriesStart,
        module='stock_inventory_location', type_='model')
    Pool.register(
        CreateInventories,
        module='stock_inventory_location', type_='wizard')
