# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import os
import unittest

from trytond.tests.test_tryton import (
    ModuleTestCase, doctest_checker, doctest_teardown)
from trytond.tests.test_tryton import suite as test_suite


class ShippingUpsTestCase(ModuleTestCase):
    'Test Shipping Ups module'
    module = 'stock_package_shipping_ups'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ShippingUpsTestCase))
    if (os.getenv('UPS_USER_ID')
            and os.getenv('UPS_PASSWORD')
            and os.getenv('UPS_LICENSE')
            and os.getenv('UPS_ACCOUNT_NUMBER')):
        suite.addTests(doctest.DocFileSuite('scenario_shipping_ups.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
                checker=doctest_checker))
    return suite
