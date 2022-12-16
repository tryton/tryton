# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .sale import *
from .product import *
from . import configuration


def register():
    Pool.register(
        Party,
        PartySalePriceList,
        Sale,
        SaleLine,
        Product,
        configuration.Configuration,
        configuration.ConfigurationSalePriceList,
        module='sale_price_list', type_='model')
