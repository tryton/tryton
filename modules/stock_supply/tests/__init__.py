# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_supply.tests.test_stock_supply import suite
except ImportError:
    from .test_stock_supply import suite

__all__ = ['suite']
