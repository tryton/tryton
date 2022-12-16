#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view
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

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('company')

    def test0010company(self):
        '''
        Create company.
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
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
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
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
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            company1_id = self.company.search([
                ('name', '=', 'B2CK'),
                ], 0, 1, None)[0]

            employee1_id = self.employee.create({
                'name': 'Employee1',
                'company': company1_id,
                })
            transaction.cursor.commit()

def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.currency.tests import test_currency
    for test in test_currency.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(CompanyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
