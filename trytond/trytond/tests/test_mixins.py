#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import socket
import urllib

from trytond.config import CONFIG
from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    install_module)
from trytond.transaction import Transaction


class UrlTestCase(unittest.TestCase):
    "Test URL generation"

    def setUp(self):
        install_module('test')
        self.urlmodel = POOL.get('test.urlobject')
        self.urlwizard = POOL.get('test.test_wizard', type='wizard')
        self.hostname = socket.getfqdn()

    def testModelURL(self):
        "Test model URLs"
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.urlmodel.get_url(),
                'tryton://%s/%s/model/test.urlobject' % (self.hostname,
                    urllib.quote(DB_NAME)))

            server_name = 'michaelscott.paper.test'
            CONFIG['hostname_jsonrpc'] = server_name
            self.assertEqual(self.urlmodel.get_url(),
                'tryton://%s/%s/model/test.urlobject' % (server_name,
                    urllib.quote(DB_NAME)))

    def testWizardURL(self):
        "Test wizard URLs"
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            CONFIG['hostname_jsonrpc'] = None
            self.assertEqual(self.urlwizard.get_url(),
                'tryton://%s/%s/wizard/test.test_wizard' % (self.hostname,
                    urllib.quote(DB_NAME)))

            server_name = 'michaelscott.paper.test'
            CONFIG['hostname_jsonrpc'] = server_name
            self.assertEqual(self.urlwizard.get_url(),
                'tryton://%s/%s/wizard/test.test_wizard' % (server_name,
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
