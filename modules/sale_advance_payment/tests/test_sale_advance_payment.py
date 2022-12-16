# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown, doctest_checker


class SaleAdvancePaymentTestCase(ModuleTestCase):
    'Test Sale Advance Payment module'
    module = 'sale_advance_payment'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            SaleAdvancePaymentTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_advance_payment.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
