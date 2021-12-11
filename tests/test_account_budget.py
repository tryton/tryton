# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import unittest

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class AccountBudgetTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Account Budget module'
    module = 'account_budget'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountBudgetTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_budget.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
