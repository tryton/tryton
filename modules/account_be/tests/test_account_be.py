# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class AccountBETestCase(ModuleTestCase):
    'Test Account BE module'
    module = 'account_be'
    language = 'fr'

    @with_transaction()
    def test_create_chart(self):
        company = create_company()
        with set_company(company):
            create_chart(company, chart=self.module + '.root_' + self.language)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountBETestCase))
    return suite
