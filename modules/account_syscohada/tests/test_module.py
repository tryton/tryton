# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import create_company, set_company
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountSYSCOHADATestCase(ModuleTestCase):
    "Test Account SYSCOHADA module"
    module = 'account_syscohada'
    language = 'fr'

    @with_transaction()
    def test_create_chart_2001(self):
        company = create_company()
        with set_company(company):
            create_chart(
                company, chart=self.module + '.root_2001_' + self.language)

    @with_transaction()
    def test_create_chart_2016(self):
        company = create_company()
        with set_company(company):
            create_chart(
                company, chart=self.module + '.root_2016_' + self.language)


del ModuleTestCase
