# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import customs
from . import product


def register():
    Pool.register(
        customs.TariffCode,
        customs.DutyRate,
        product.Category,
        product.Template,
        product.Product_TariffCode,
        product.Product,
        module='customs', type_='model')
