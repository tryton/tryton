#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests
from trytond.tests import RPCProxy, CONTEXT, SOCK


class CompanyTestCase(unittest.TestCase):
    '''
    Test Company module.
    '''

    def setUp(self):
        trytond.tests.install_module('company')
        self.company = RPCProxy('company.company')
        self.employee = RPCProxy('company.employee')
        self.currency = RPCProxy('currency.currency')

    def test0010company(self):
        '''
        Create company.
        '''
        currency1_id = self.currency.search([
            ('code', '=', 'EUR'),
            ], 0, 1, None, CONTEXT)[0]

        company1_id = self.company.create({
            'name': 'B2CK',
            'currency': currency1_id,
            }, CONTEXT)
        self.assert_(company1_id)

    def test0020company_recursion(self):
        '''
        Test company recursion.
        '''
        currency1_id = self.currency.search([
            ('code', '=', 'EUR'),
            ], 0, 1, None, CONTEXT)[0]

        company1_id = self.company.search([
            ('name', '=', 'B2CK'),
            ], 0, 1, None, CONTEXT)[0]

        company2_id = self.company.create({
            'name': 'B2CK Branch',
            'parent': company1_id,
            'currency': currency1_id,
            }, CONTEXT)
        self.assert_(company2_id)

        self.failUnlessRaises(Exception, self.company.write,
                company1_id, {
                    'parent': company2_id,
                }, CONTEXT)

    def test0030employe(self):
        '''
        Create employee.
        '''
        company1_id = self.company.search([
            ('name', '=', 'B2CK'),
            ], 0, 1, None, CONTEXT)[0]

        employee1_id = self.employee.create({
            'name': 'Employee1',
            'company': company1_id,
            }, CONTEXT)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CompanyTestCase)

if __name__ == '__main__':
    suiteTrytond = trytond.tests.suite()
    suiteCompany = suite()
    alltests = unittest.TestSuite([suiteTrytond, suiteCompany])
    unittest.TextTestRunner(verbosity=2).run(alltests)
    SOCK.disconnect()
