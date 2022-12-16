# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.analytic_purchase.tests.test_analytic_purchase import suite  # noqa: E501
except ImportError:
    from .test_analytic_purchase import suite

__all__ = ['suite']
