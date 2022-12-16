# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .sale import *
from . import product
from . import configuration


def register():
    Pool.register(
        Party,
        PartySalePriceList,
        Sale,
        SaleLine,
        product.Product,
        product.PriceList,
        configuration.Configuration,
        configuration.ConfigurationSalePriceList,
        module='sale_price_list', type_='model')
