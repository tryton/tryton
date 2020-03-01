# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.product_measurements.tests.test_product_measurements import suite  # noqa: E501
except ImportError:
    from .test_product_measurements import suite

__all__ = ['suite']
