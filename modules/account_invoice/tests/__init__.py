# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_invoice.tests.test_account_invoice import (
        suite, set_invoice_sequences)
except ImportError:
    from .test_account_invoice import suite, set_invoice_sequences

__all__ = ['suite', 'set_invoice_sequences']
