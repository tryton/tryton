#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class AccountTestCase(unittest.TestCase):
    '''
    Test Account module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('account')
        self.account_template = POOL.get('account.account.template')
        self.account = POOL.get('account.account')
        self.account_create_chart_account = POOL.get(
                'account.account.create_chart_account', type='wizard')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('account')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010account_chart(self):
        'Test creation of minimal chart of accounts'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            account_template_id, = self.account_template.search([
                ('parent', '=', False),
                ])
            company_id, = self.company.search([('name', '=', 'B2CK')])
            self.user.write(USER, {
                    'main_company': company_id,
                    'company': company_id,
                    })

            self.account_create_chart_account._action_create_account({
                    'form': {
                        'account_template': account_template_id,
                        'company': company_id,
                        },
                    })
            receivable_id, = self.account.search([
                    ('kind', '=', 'receivable'),
                    ('company', '=', company_id),
                    ])
            payable_id, = self.account.search([
                    ('kind', '=', 'payable'),
                    ('company', '=', company_id),
                    ])
            self.account_create_chart_account._action_create_properties({
                    'form': {
                        'company': company_id,
                        'account_receivable': receivable_id,
                        'account_payable': payable_id,
                        },
                    })
            transaction.cursor.commit()

def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
