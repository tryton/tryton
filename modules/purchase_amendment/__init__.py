# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase

__all__ = ['register']


def register():
    Pool.register(
        purchase.Purchase,
        purchase.Amendment,
        purchase.AmendmentLine,
        module='purchase_amendment', type_='model')
