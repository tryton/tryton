# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class AccountTaxRuleCountryTestCase(ModuleTestCase):
    'Test Account Tax Rule Country module'
    module = 'account_tax_rule_country'

    @with_transaction()
    def test_account_chart(self):
        'Test creation and update of minimal chart of accounts'
        pool = Pool()
        Account = pool.get('account.account')
        UpdateChart = pool.get('account.update_chart', type='wizard')

        company = create_company()
        with set_company(company):
            create_chart(company, tax=True)
            root, = Account.search([('parent', '=', None)])

            session_id, _, _ = UpdateChart.create()
            update_chart = UpdateChart(session_id)
            update_chart.start.account = root
            update_chart.transition_update()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountTaxRuleCountryTestCase))
    return suite
