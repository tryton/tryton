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


class RelationshipTestCase(unittest.TestCase):
    '''
    Test Relationship module.
    '''

    def setUp(self):
        trytond.tests.install_module('relationship')
        self.category = RPCProxy('relationship.category')
        self.party = RPCProxy('relationship.party')
        self.address = RPCProxy('relationship.address')
        self.country = RPCProxy('relationship.country')

    def test0010category(self):
        '''
        Create category.
        '''
        category1_id = self.category.create({
            'name': 'Category 1',
            }, CONTEXT)
        self.assert_(category1_id)

    def test0020category_recursion(self):
        '''
        Test category recursion.
        '''
        category1_id = self.category.search([
            ('name', '=', 'Category 1'),
            ], 0, 1, None, CONTEXT)[0]

        category2_id = self.category.create({
            'name': 'Category 2',
            'parent': category1_id,
            }, CONTEXT)
        self.assert_(category2_id)

        self.failUnlessRaises(Exception, self.category.write,
                category1_id, {
                    'parent': category2_id,
                }, CONTEXT)

    def test0030party(self):
        '''
        Create party.
        '''
        party1_id = self.party.create({
            'name': 'Party 1',
            }, CONTEXT)
        self.assert_(party1_id)

    def test0040party_code(self):
        '''
        Test party code constraint.
        '''
        party1_id = self.party.search([], 0, 1, None, CONTEXT)[0]

        code = self.party.read(party1_id, ['code'], CONTEXT)['code']

        party2_id = self.party.create({
            'name': 'Party 2',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.party.write, party2_id, {
            'code': code,
            }, CONTEXT)

    def test0050address(self):
        '''
        Create address.
        '''
        party1_id = self.party.search([], 0, 1, None, CONTEXT)[0]
        belgium_id = self.country.search([
            ('code', '=', 'BE'),
            ], 0, 1, None, CONTEXT)[0]

        address1_id = self.address.create({
            'party': party1_id,
            'street': 'St sample, 15',
            'city': 'City',
            'country': belgium_id,
            }, CONTEXT)
        self.assert_(party1_id)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RelationshipTestCase)

if __name__ == '__main__':
    suiteTrytond = trytond.tests.suite()
    suiteRelationship = suite()
    alltests = unittest.TestSuite([suiteTrytond, suiteRelationship])
    unittest.TextTestRunner(verbosity=2).run(alltests)
    SOCK.disconnect()
