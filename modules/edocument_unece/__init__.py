# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import account

__all__ = ['register']


def register():
    Pool.register(
        product.Uom,
        account.TaxTemplate,
        account.Tax,
        module='edocument_unece', type_='model')
    Pool.register(
        module='edocument_unece', type_='wizard')
    Pool.register(
        module='edocument_unece', type_='report')
