# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.product_kit.tests.test_product_kit import suite  # noqa: E501
except ImportError:
    from .test_product_kit import suite

__all__ = ['suite']
