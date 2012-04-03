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
from trytond.tests.test_tryton import test_view, test_depends
from trytond.modules.party_siret import luhn


class PartySiretTestCase(unittest.TestCase):
    '''
    Test PartySiret module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('party_siret')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('party_siret')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010luhn(self):
        '''
        Test luhn.
        '''
        values = (
                (4111111111111111, True),
                ('4111111111111111', True),
                (4222222222222, True),
                (378734493671000, True),
                (5424000000000015, True),
                (5555555555554444, True),
                (1008, True),
                ('0000001008', True),
                ('000000001008', True),
                (4012888888881881, True),
                (1234567890123456789012345678909, True),
                (4111111111211111, False),
                (42222222222224, False),
                (100, False),
                ('100', False),
                ('0000100', False),
                ('abc', False),
                (None, False),
                (object(), False),
            )
        for value, test in values:
            self.assert_(luhn.validate(value) == test)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        PartySiretTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
