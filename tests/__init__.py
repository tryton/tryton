# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.stock_quantity_early_planning.tests.test_stock_quantity_early_planning import suite  # noqa: E501
except ImportError:
    from .test_stock_quantity_early_planning import suite

__all__ = ['suite']
