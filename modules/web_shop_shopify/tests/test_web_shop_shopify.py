# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import doctest
import os
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class WebShopShopifyTestCase(ModuleTestCase):
    'Test Web Shop Shopify module'
    module = 'web_shop_shopify'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            WebShopShopifyTestCase))
    if os.getenv('SHOPIFY_PASSWORD') and os.getenv('SHOPIFY_URL'):
        suite.addTests(doctest.DocFileSuite(
                'scenario_web_shop_shopify.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
        suite.addTests(doctest.DocFileSuite(
                'scenario_web_shop_shopify_secondary_unit.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
