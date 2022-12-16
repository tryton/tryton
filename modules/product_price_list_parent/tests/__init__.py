# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.product_price_list_parent.tests.test_product_price_list_parent import suite  # noqa: E501
except ImportError:
    from .test_product_price_list_parent import suite

__all__ = ['suite']
