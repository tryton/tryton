# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product
from . import production
from . import sale

__all__ = ['register']


def register():
    Pool.register(
        product.Template,
        product.Product,
        production.Production,
        sale.Sale,
        sale.Line,
        module='sale_supply_production', type_='model')
    Pool.register(
        module='sale_supply_production', type_='wizard')
    Pool.register(
        module='sale_supply_production', type_='report')
