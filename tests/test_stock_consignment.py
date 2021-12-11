# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import unittest

from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class StockConsignmentTestCase(ModuleTestCase):
    'Test Stock Consignment module'
    module = 'stock_consignment'
    extras = ['stock_supply']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockConsignmentTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_consignment.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_consignment_supplier_customer.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
