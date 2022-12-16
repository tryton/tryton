#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests
import trytond.modules.company.tests
from trytond.tests import RPCProxy, CONTEXT, SOCK


class AccountTestCase(unittest.TestCase):
    '''
    Test Account module.
    '''

    def setUp(self):
        trytond.tests.install_module('account')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(AccountTestCase)

if __name__ == '__main__':
    suiteTrytond = trytond.tests.suite()
    suiteCompany = trytond.modules.company.tests.suite()
    suiteAccount = suite()
    alltests = unittest.TestSuite([suiteTrytond, suiteCompany, suiteAccount])
    unittest.TextTestRunner(verbosity=2).run(alltests)
    SOCK.disconnect()
