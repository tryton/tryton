# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class StockSupplyProductionTestCase(ModuleTestCase):
    'Test Stock Supply Production module'
    module = 'stock_supply_production'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockSupplyProductionTestCase))
    return suite
