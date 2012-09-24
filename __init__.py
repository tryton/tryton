#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .sale import *
from .product import *


def register():
    Pool.register(
        Party,
        Sale,
        SaleLine,
        Product,
        module='sale_price_list', type_='model')
