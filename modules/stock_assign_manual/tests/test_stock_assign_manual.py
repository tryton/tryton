# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

import doctest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class StockAssignManualTestCase(ModuleTestCase):
    'Test Stock Assign Manual module'
    module = 'stock_assign_manual'
    extras = ['production']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockAssignManualTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_assign_manual.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
