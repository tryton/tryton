# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import os
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class StockPackageShippingSendcloudTestCase(ModuleTestCase):
    'Test Stock Package Shipping Sendcloud module'
    module = 'stock_package_shipping_sendcloud'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockPackageShippingSendcloudTestCase))
    if (os.getenv('SENDCLOUD_PUBLIC_KEY')
            and os.getenv('SENDCLOUD_SECRET_KEY')):
        suite.addTests(doctest.DocFileSuite(
                'scenario_stock_package_shipping_sendcloud.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
