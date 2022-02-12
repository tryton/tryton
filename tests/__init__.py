# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.sale_invoice_date.tests.test_sale_invoice_date import suite  # noqa: E501, isort: skip
except ImportError:
    from .test_sale_invoice_date import suite

__all__ = ['suite']
