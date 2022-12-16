# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_location_sequence.tests.test_stock_location_sequence import suite
except ImportError:
    from .test_stock_location_sequence import suite

__all__ = ['suite']
