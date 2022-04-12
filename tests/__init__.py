# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.purchase_product_quantity.tests.test_purchase_product_quantity import suite  # noqa: E501, isort: skip
except ImportError:
    from .test_purchase_product_quantity import suite

__all__ = ['suite']
