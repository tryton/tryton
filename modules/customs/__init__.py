# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from customs import *
from product import *


def register():
    Pool.register(
        TariffCode,
        DutyRate,
        Category,
        Template,
        Product_TariffCode,
        Product,
        module='customs', type_='model')
