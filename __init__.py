#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .product import *
from .location import *


def register():
    Pool.register(
        Product,
        ProductLocation,
        ShipmentIn,
        ShipmentOutReturn,
        module='stock_product_location', type_='model')
