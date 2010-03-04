#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import logging
logging.basicConfig(level=logging.FATAL)

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view

class StockTestCase(unittest.TestCase):
    '''
    Test Stock module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock')

    def test0005views(self):
        '''
        Test views.
        '''
        self.assertRaises(Exception, test_view('stock'))

def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(StockTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
