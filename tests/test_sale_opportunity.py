# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)


class SaleOpportunityTestCase(CompanyTestMixin, ModuleTestCase):
    'Test SaleOpportunity module'
    module = 'sale_opportunity'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SaleOpportunityTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_sale_opportunity.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
