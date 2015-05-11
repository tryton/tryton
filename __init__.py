# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *


def register():
    Pool.register(
        SalePromotion,
        SalePromotion_Product,
        Sale,
        SaleLine,
        module='sale_promotion', type_='model')
