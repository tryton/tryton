# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.currency.tests.test_currency import (
        add_currency_rate, create_currency, suite)
except ImportError:
    from .test_currency import add_currency_rate, create_currency, suite

__all__ = ['suite', 'create_currency', 'add_currency_rate']
