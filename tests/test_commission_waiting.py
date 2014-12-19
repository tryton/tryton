# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

import unittest
import doctest

from trytond.tests.test_tryton import install_module, test_view, test_depends,\
    suite as test_suite, doctest_setup, doctest_teardown


class CommissionWaitingTestCase(unittest.TestCase):
    'Test Commission Waiting module'

    def setUp(self):
        install_module('commission_waiting')

    def test0005views(self):
        'Test views'
        test_view('commission_waiting')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CommissionWaitingTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_commission_waiting.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
