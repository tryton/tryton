#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import urllib

from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    install_module)
from trytond.transaction import Transaction
from trytond.url import HOSTNAME


class UrlTestCase(unittest.TestCase):
    "Test URL generation"

    def setUp(self):
        install_module('test')
        self.urlmodel = POOL.get('test.urlobject')
        self.urlwizard = POOL.get('test.test_wizard', type='wizard')
        self.hostname = HOSTNAME

    def testModelURL(self):
        "Test model URLs"
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.urlmodel.__url__,
                'tryton://%s/%s/model/test.urlobject' % (self.hostname,
                    urllib.quote(DB_NAME)))

            self.assertEqual(self.urlmodel(1).__url__,
                'tryton://%s/%s/model/test.urlobject/1' % (self.hostname,
                    urllib.quote(DB_NAME)))

    def testWizardURL(self):
        "Test wizard URLs"
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.urlwizard.__url__,
                'tryton://%s/%s/wizard/test.test_wizard' % (self.hostname,
                    urllib.quote(DB_NAME)))


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (UrlTestCase,):
        suite.addTests(func(testcase))
    return suite

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
