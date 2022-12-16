# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_package_shipping_ups.tests.test_shipping_ups import suite  # noqa: E501
except ImportError:
    from .test_shipping_ups import suite

__all__ = ['suite']
