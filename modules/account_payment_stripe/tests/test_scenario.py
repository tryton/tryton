# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

from trytond.tests.test_tryton import TEST_NETWORK, load_doc_tests


def load_tests(*args, **kwargs):
    if (not TEST_NETWORK
            or not (os.getenv('STRIPE_SECRET_KEY')
                and os.getenv('STRIPE_PUBLISHABLE_KEY'))):
        kwargs.setdefault('skips', set()).update({
                'scenario_account_payment_stripe.rst',
                'scenario_account_payment_stripe_dispute.rst',
                'scenario_account_payment_stripe_identical.rst',
                'scenario_account_payment_stripe_intent.rst',
                'scenario_account_payment_stripe_refund_failure.rst',
                })
    return load_doc_tests(__name__, __file__, *args, **kwargs)
