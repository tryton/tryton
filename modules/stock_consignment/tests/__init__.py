# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_consignment.tests.test_stock_consignment import suite  # noqa: E501
except ImportError:
    from .test_stock_consignment import suite

__all__ = ['suite']
