# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

import doctest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker

from trytond.modules.company.tests import CompanyTestMixin


class StockQuantityEarlyPlanningTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Stock Quantity Early Planning module'
    module = 'stock_quantity_early_planning'
    extras = ['production']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockQuantityEarlyPlanningTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_quantity_early_planning.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
