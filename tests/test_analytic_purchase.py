# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import test_view, test_depends, test_menu_action


class AnalyticPurchaseTestCase(ModuleTestCase):
    'Test AnalyticPurchase module'
    module = 'analytic_purchase'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AnalyticPurchaseTestCase))
    return suite
