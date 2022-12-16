# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import sale
from . import product
from . import configuration


def register():
    Pool.register(
        party.Party,
        party.PartySalePriceList,
        sale.Sale,
        sale.Line,
        product.Product,
        product.PriceList,
        product.SaleContext,
        configuration.Configuration,
        configuration.ConfigurationSalePriceList,
        module='sale_price_list', type_='model')
