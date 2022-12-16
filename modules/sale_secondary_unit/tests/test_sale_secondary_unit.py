# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

import doctest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class SaleSecondaryUnitTestCase(ModuleTestCase):
    'Test Sale Secondary Unit module'
    module = 'sale_secondary_unit'
    extras = [
        'account_invoice_secondary_unit', 'stock_secondary_unit',
        'sale_product_customer']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            SaleSecondaryUnitTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_secondary_unit.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
