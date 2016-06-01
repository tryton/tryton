# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_package_shipping.tests.tes_shipping import suite
except ImportError:
    from .test_shipping import suite

__all__ = ['suite']
