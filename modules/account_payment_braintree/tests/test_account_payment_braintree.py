# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import unittest

import doctest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class AccountPaymentBraintreeTestCase(ModuleTestCase):
    'Test Account Payment Braintree module'
    module = 'account_payment_braintree'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountPaymentBraintreeTestCase))
    if (os.getenv('BRAINTREE_MERCHANT_ID')
            and os.getenv('BRAINTREE_PUBLIC_KEY')
            and os.getenv('BRAINTREE_PRIVATE_KEY')):
        suite.addTests(doctest.DocFileSuite(
                'scenario_account_payment_braintree.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
