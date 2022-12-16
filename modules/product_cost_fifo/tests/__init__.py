# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.product_cost_fifo.tests.test_product_cost_fifo import suite
except ImportError:
    from .test_product_cost_fifo import suite

__all__ = ['suite']
