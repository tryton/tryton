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
from trytond.tests.test_tryton import RPCProxy, CONTEXT, SOCK

class StockTestCase(unittest.TestCase):
    '''
    Test Stock module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock')
        self.location = RPCProxy('stock.location')

    def test0990location(self):
        '''
        Create locations.
        '''
        storage_id = self.location.search([
            ('code', '=', 'STO'),
            ], CONTEXT)[0]

        new_locations = [storage_id]

        for j in range(5):
            parent_locations = new_locations
            new_locations = []
            for parent_location in parent_locations:
                for i in range(4):
                    location_id = self.location.create({
                        'name': 'Test ' + str(j) + ' ' + str(i),
                        'parent': parent_location,
                        'type': 'storage',
                        }, CONTEXT)
                    new_locations.append(location_id)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(StockTestCase)

if __name__ == '__main__':
    suiteTrytond = trytond.tests.test_tryton.suite()
    suiteStock = suite()
    alltests = unittest.TestSuite([suiteTrytond, suiteStock])
    unittest.TextTestRunner(verbosity=2).run(alltests)
    SOCK.disconnect()
