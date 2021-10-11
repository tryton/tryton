# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import os
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class StockPackageShippingMyglsTestCase(ModuleTestCase):
    'Test Stock Package Shipping Mygls module'
    module = 'stock_package_shipping_mygls'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockPackageShippingMyglsTestCase))
    if (os.getenv('MYGLS_USERNAME')
            and os.getenv('MYGLS_PASSWORD')
            and os.getenv('MYGLS_CLIENT_NUMBER')):
        suite.addTests(doctest.DocFileSuite(
                'scenario_stock_package_shipping_mygls.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
