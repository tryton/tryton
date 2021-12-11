# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.modules.company.tests import (
    CompanyTestMixin, PartyCompanyCheckEraseMixin)
from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)


class SaleSupplyDropShipmentTestCase(
        PartyCompanyCheckEraseMixin, CompanyTestMixin, ModuleTestCase):
    'Test SaleSupplyDropShipment module'
    module = 'sale_supply_drop_shipment'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            SaleSupplyDropShipmentTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_supply_drop_shipment.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_supply_drop_shipment_remaining_qty.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_supply_drop_shipment_on_invoice.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
