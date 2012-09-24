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
            currency1, = self.currency.search([
                    ('code', '=', 'cu1'),
                    ], 0, 1, None)

            company1 = self.company.create({
                    'name': 'B2CK',
                    'currency': currency1.id,
                    })
            self.assert_(company1)
            transaction.cursor.commit()

    def test0020company_recursion(self):
        '''
        Test company recursion.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            currency1, = self.currency.search([
                ('code', '=', 'cu1'),
                ], 0, 1, None)

            company1, = self.company.search([
                    ('name', '=', 'B2CK'),
                    ], 0, 1, None)

            company2 = self.company.create({
                    'name': 'B2CK Branch',
                    'parent': company1.id,
                    'currency': currency1.id,
                    })
            self.assert_(company2)

            self.assertRaises(Exception, self.company.write,
                [company1], {
                    'parent': company2.id,
                    })

    def test0030employe(self):
        '''
        Create employee.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company1, = self.company.search([
                    ('name', '=', 'B2CK'),
                    ], 0, 1, None)

            self.employee.create({
                    'name': 'Employee1',
                    'company': company1.id,
                    })
            transaction.cursor.commit()

    def test0040user(self):
        '''
        Test user company
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency1, = self.currency.search([
                    ('code', '=', 'cu1'),
                    ], 0, 1, None)

            company1, = self.company.search([
                    ('name', '=', 'B2CK'),
                    ], 0, 1, None)

            company2 = self.company.create({
                    'name': 'B2CK Branch',
                    'parent': company1.id,
                    'currency': currency1.id,
                    })
            user1 = self.user.create({
                    'name': 'Test 1',
                    'login': 'test1',
                    'main_company': company1.id,
                    'company': company1.id,
                    })
            user2 = self.user.create({
                    'name': 'Test 2',
                    'login': 'test2',
                    'main_company': company2.id,
                    'company': company2.id,
                    })
            self.assert_(user1)

            with transaction.set_user(user1.id):
                user1, user2 = self.user.browse([user1.id, user2.id])
                self.assertEqual(user1.company, company1)
                self.assertEqual(user2.company, company2)

                with transaction.set_context({'company': company2.id}):
                    user1, user2 = self.user.browse([user1.id, user2.id])
                    self.assertEqual(user1.company, company2)
                    self.assertEqual(user2.company, company2)

                with transaction.set_context({'company': None}):
                    user1, user2 = self.user.browse([user1.id, user2.id])
                    self.assertEqual(user1.company, None)
                    self.assertEqual(user2.company, company2)


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
