# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale

__all__ = ['register']


def register():
    Pool.register(
        sale.Sale,
        sale.Line,
        sale.LineTax,
        module='sale_history', type_='model')
