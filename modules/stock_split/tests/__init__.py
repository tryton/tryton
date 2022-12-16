# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_split.tests.test_stock_split import suite
except ImportError:
    from .test_stock_split import suite

__all__ = ['suite']
