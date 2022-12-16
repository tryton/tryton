# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import sale

__all__ = ['register']


def register():
    Pool.register(
        sale.Sale,
        sale.Amendment,
        sale.AmendmentLine,
        module='sale_amendment', type_='model')
