# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool


def register():
    # Prevent to import backend when importing scripts
    from . import currency
    from . import ir
    Pool.register(
        currency.Currency,
        currency.CurrencyRate,
        currency.Cron,
        currency.Cron_Currency,
        ir.Cron,
        module='currency', type_='model')
