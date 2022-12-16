# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_teardown, doctest_checker, with_transaction)

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class AccountFRTestCase(ModuleTestCase):
    'Test Account FR module'
    module = 'account_fr'

    @with_transaction()
    def test_create_chart(self):
        company = create_company()
        with set_company(company):
            create_chart(company, chart=self.module + '.root')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountFRTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_fec.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
