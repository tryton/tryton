# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown, doctest_checker


class StockInventoryLocationTestCase(ModuleTestCase):
    'Test StockInventoryLocation module'
    module = 'stock_inventory_location'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockInventoryLocationTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_inventories.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
