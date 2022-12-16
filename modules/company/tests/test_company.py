#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class CompanyTestCase(unittest.TestCase):
    '''
    Test Company module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('company')
        self.company = POOL.get('company.company')
        self.employee = POOL.get('company.employee')
        self.currency = POOL.get('currency.currency')
        self.user = POOL.get('res.user')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('company')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010company(self):
        '''
        Create company.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency1_id = self.currency.search([
                ('code', '=', 'cu1'),
                ], 0, 1, None)[0]

            company1_id = self.company.create({
                'name': 'B2CK',
                'currency': currency1_id,
                })
            self.assert_(company1_id)
            transaction.cursor.commit()

    def test0020company_recursion(self):
        '''
        Test company recursion.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            currency1_id = self.currency.search([
                ('code', '=', 'cu1'),
                ], 0, 1, None)[0]

            company1_id = self.company.search([
                ('name', '=', 'B2CK'),
                ], 0, 1, None)[0]

            company2_id = self.company.create({
                'name': 'B2CK Branch',
                'parent': company1_id,
                'currency': currency1_id,
                })
            self.assert_(company2_id)

            self.failUnlessRaises(Exception, self.company.write,
                    company1_id, {
                        'parent': company2_id,
                    })

    def test0030employe(self):
        '''
        Create employee.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company1_id = self.company.search([
                ('name', '=', 'B2CK'),
                ], 0, 1, None)[0]

            self.employee.create({
                'name': 'Employee1',
                'company': company1_id,
                })
            transaction.cursor.commit()

    def test0040user(self):
        '''
        Test user company
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency1_id = self.currency.search([
                ('code', '=', 'cu1'),
                ], 0, 1, None)[0]

            company1_id = self.company.search([
                ('name', '=', 'B2CK'),
                ], 0, 1, None)[0]

            company2_id = self.company.create({
                'name': 'B2CK Branch',
                'parent': company1_id,
                'currency': currency1_id,
                })
            user1_id = self.user.create({
                'name': 'Test 1',
                'login': 'test1',
                'main_company': company1_id,
                'company': company1_id,
            })
            user2_id = self.user.create({
                'name': 'Test 2',
                'login': 'test2',
                'main_company': company2_id,
                'company': company2_id,
            })
            self.assert_(user1_id)

            with transaction.set_user(user1_id):
                company_id = self.user.read(user1_id, ['company'])['company']
                self.assertEqual(company_id, company1_id)

                user1, user2 = self.user.browse([user1_id, user2_id])
                self.assertEqual(user1.company.id, company1_id)
                self.assertEqual(user2.company.id, company2_id)

                with transaction.set_context({'company': company2_id}):
                    company_id = self.user.read(user1_id,
                        ['company'])['company']
                    self.assertEqual(company_id, company2_id)

                    user1, user2 = self.user.browse([user1_id, user2_id])
                    self.assertEqual(user1.company.id, company2_id)
                    self.assertEqual(user2.company.id, company2_id)

                with transaction.set_context({'company': False}):
                    company_id = self.user.read(user1_id,
                        ['company'])['company']
                    self.assertEqual(company_id, False)

                    user1, user2 = self.user.browse([user1_id, user2_id])
                    self.assertEqual(user1.company.id, None)
                    self.assertEqual(user2.company.id, company2_id)


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.currency.tests import test_currency
    for test in test_currency.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CompanyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
