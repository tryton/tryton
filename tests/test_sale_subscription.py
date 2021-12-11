# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import unittest

from trytond.modules.company.tests import (
    CompanyTestMixin, PartyCompanyCheckEraseMixin)
from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class SaleSubscriptionTestCase(
        PartyCompanyCheckEraseMixin, CompanyTestMixin, ModuleTestCase):
    'Test Sale Subscription module'
    module = 'sale_subscription'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            SaleSubscriptionTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_subscription.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_subscription_new_line.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_subscription_advanced_invoice.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
