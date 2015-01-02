# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends, test_menu_action


class CountryTestCase(unittest.TestCase):
    'Test Country module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('country')

    def test0005views(self):
        'Test views'
        test_view('country')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0007menu_actions(self):
        'Test menu actions'
        test_menu_action('country')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CountryTestCase))
    return suite
