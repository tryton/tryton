# This file is part purchase_request_for_quotation module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

try:
    from trytond.modules.purchase_request_quotation.tests.test_purchase_request_quotation import suite
except ImportError:
    from .test_purchase_request_quotation import suite

__all__ = ['suite']
