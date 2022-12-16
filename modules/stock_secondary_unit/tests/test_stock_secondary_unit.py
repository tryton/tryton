# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest


from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class StockSecondaryUnitTestCase(ModuleTestCase):
    'Test Stock Secondary Unit module'
    module = 'stock_secondary_unit'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockSecondaryUnitTestCase))
    return suite
