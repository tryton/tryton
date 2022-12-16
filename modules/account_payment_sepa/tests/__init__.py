# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_payment_sepa.tests.test_account_payment_sepa import (
        suite, validate_file)
except ImportError:
    from .test_account_payment_sepa import suite, validate_file

__all__ = ['suite', 'validate_file']
