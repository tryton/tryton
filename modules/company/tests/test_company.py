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
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, test_view


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
        self.assertRaises(Exception, test_view('company'))

    def test0010company(self):
        '''
        Create company.
        '''
        cursor = DB.cursor()
        currency1_id = self.currency.search(cursor, USER, [
            ('code', '=', 'cu1'),
            ], 0, 1, None, CONTEXT)[0]

        company1_id = self.company.create(cursor, USER, {
            'name': 'B2CK',
            'currency': currency1_id,
            }, CONTEXT)
        self.assert_(company1_id)
        cursor.commit()
        cursor.close()

    def test0020company_recursion(self):
        '''
        Test company recursion.
        '''
        cursor = DB.cursor()
        currency1_id = self.currency.search(cursor, USER, [
            ('code', '=', 'cu1'),
            ], 0, 1, None, CONTEXT)[0]

        company1_id = self.company.search(cursor, USER, [
            ('name', '=', 'B2CK'),
            ], 0, 1, None, CONTEXT)[0]

        company2_id = self.company.create(cursor, USER, {
            'name': 'B2CK Branch',
            'parent': company1_id,
            'currency': currency1_id,
            }, CONTEXT)
        self.assert_(company2_id)

        self.failUnlessRaises(Exception, self.company.write,
                cursor, USER, company1_id, {
                    'parent': company2_id,
                }, CONTEXT)
        cursor.commit()
        cursor.close()

    def test0030employe(self):
        '''
        Create employee.
        '''
        cursor = DB.cursor()
        company1_id = self.company.search(cursor, USER, [
            ('name', '=', 'B2CK'),
            ], 0, 1, None, CONTEXT)[0]

        employee1_id = self.employee.create(cursor, USER, {
            'name': 'Employee1',
            'company': company1_id,
            }, CONTEXT)
        cursor.commit()
        cursor.close()

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
