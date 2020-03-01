# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.purchase_invoice_line_standalone.tests.test_purchase_invoice_line_standalone import suite  # noqa: E501
except ImportError:
    from .test_purchase_invoice_line_standalone import suite

__all__ = ['suite']
