# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import os
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown, doctest_checker


class StockPackageShippingDpdTestCase(ModuleTestCase):
    'Test Stock Package Shipping Dpd module'
    module = 'stock_package_shipping_dpd'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockPackageShippingDpdTestCase))
    if os.getenv('DPD_USER_ID') and os.getenv('DPD_PASSWORD'):
        suite.addTests(doctest.DocFileSuite('scenario_shipping_dpd.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
                checker=doctest_checker))
    return suite
