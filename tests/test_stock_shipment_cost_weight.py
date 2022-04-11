# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest

from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class StockShipmentCostWeightTestCase(ModuleTestCase):
    'Test Stock Shipment Cost Weight module'
    module = 'stock_shipment_cost_weight'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockShipmentCostWeightTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_shipment_cost_weight.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
