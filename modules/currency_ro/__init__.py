# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import currency

__all__ = ['register']


def register():
    Pool.register(
        currency.Cron,
        module='currency_ro', type_='model')
