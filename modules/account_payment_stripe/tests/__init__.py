# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_payment_stripe.tests.test_account_payment_stripe import suite
except ImportError:
    from .test_account_payment_stripe import suite

__all__ = ['suite']
