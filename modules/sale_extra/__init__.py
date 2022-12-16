# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .price_list import *


def register():
    Pool.register(
        SaleExtra,
        SaleExtraLine,
        Sale,
        SaleLine,
        PriceList,
        module='sale_extra', type_='model')
