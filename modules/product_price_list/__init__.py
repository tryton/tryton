# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import price_list


def register():
    Pool.register(
        price_list.PriceList,
        price_list.PriceListLine,
        module='product_price_list', type_='model')
