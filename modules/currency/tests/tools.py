# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from proteus import Model

__all__ = ['get_currency']

_names = {
    'USD': 'U.S. Dollar',
    'EUR': 'Euro',
    }
_symbols = {
    'USD': '$',
    'EUR': '€',
    }
_rates = {
    'USD': Decimal('1.0'),
    'EUR': Decimal('2.0'),
    }


def get_currency(code='USD', config=None):
    "Get currency with code"
    Currency = Model.get('currency.currency', config=config)
    CurrencyRate = Model.get('currency.currency.rate', config=config)

    currencies = Currency.find([('code', '=', code)])
    if not currencies:
        currency = Currency(name=_names.get(code, code),
            symbol=_symbols.get(code), code=code,
            rounding=Decimal('0.01'))
        currency.save()
        rate = _rates.get(code)
        if rate is not None:
            CurrencyRate(date=datetime.date.min, rate=rate,
                currency=currency).save()
    else:
        currency, = currencies
    return currency
