# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class AccountPaymentTestCase(unittest.TestCase):
    'Test Account Payment module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('account_payment_clearing')

    def test0005views(self):
        'Test views'
        test_view('account_payment_clearing')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountPaymentTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_payment_clearing.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
