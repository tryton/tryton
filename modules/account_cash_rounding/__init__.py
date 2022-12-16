# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account
from . import currency
from . import purchase
from . import sale

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.ConfigurationCashRoundingAccount,
        currency.Currency,
        module='account_cash_rounding', type_='model')
    Pool.register(
        account.Invoice,
        module='account_cash_rounding', type_='model',
        depends=['account_invoice'])
    Pool.register(
        purchase.Purchase,
        module='account_cash_rounding', type_='model',
        depends=['purchase'])
    Pool.register(
        sale.Sale,
        module='account_cash_rounding', type_='model',
        depends=['sale'])
