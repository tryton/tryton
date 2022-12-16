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


class PartyTestCase(unittest.TestCase):
    '''
    Test Party module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('party')
        self.category = POOL.get('party.category')
        self.party = POOL.get('party.party')
        self.address = POOL.get('party.address')
        self.cursor = DB.cursor()

    def tearDown(self):
        self.cursor.commit()
        self.cursor.close()

    def test0005views(self):
        '''
        Test views.
        '''
        self.assertRaises(Exception, test_view('party'))

    def test0010category(self):
        '''
        Create category.
        '''
        category1_id = self.category.create(self.cursor, USER, {
            'name': 'Category 1',
            }, CONTEXT)
        self.assert_(category1_id)

    def test0020category_recursion(self):
        '''
        Test category recursion.
        '''
        category1_id = self.category.search(self.cursor, USER, [
            ('name', '=', 'Category 1'),
            ], 0, 1, None, CONTEXT)[0]

        category2_id = self.category.create(self.cursor, USER, {
            'name': 'Category 2',
            'parent': category1_id,
            }, CONTEXT)
        self.assert_(category2_id)

        self.failUnlessRaises(Exception, self.category.write, self.cursor,
                USER, category1_id, {
                    'parent': category2_id,
                }, CONTEXT)

    def test0030party(self):
        '''
        Create party.
        '''
        party1_id = self.party.create(self.cursor, USER, {
            'name': 'Party 1',
            }, CONTEXT)
        self.assert_(party1_id)

    def test0040party_code(self):
        '''
        Test party code constraint.
        '''
        party1_id = self.party.search(self.cursor, USER, [], 0, 1, None,
                CONTEXT)[0]

        code = self.party.read(self.cursor, USER, party1_id, ['code'],
                CONTEXT)['code']

        party2_id = self.party.create(self.cursor, USER, {
            'name': 'Party 2',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.party.write, self.cursor, USER,
                party2_id, {
                    'code': code,
                }, CONTEXT)

    def test0050address(self):
        '''
        Create address.
        '''
        party1_id = self.party.search(self.cursor, USER, [], 0, 1, None,
                CONTEXT)[0]

        address1_id = self.address.create(self.cursor, USER, {
            'party': party1_id,
            'street': 'St sample, 15',
            'city': 'City',
            }, CONTEXT)
        self.assert_(party1_id)

def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PartyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
