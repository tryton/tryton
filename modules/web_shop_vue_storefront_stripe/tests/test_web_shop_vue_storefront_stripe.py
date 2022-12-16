# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class WebShopVueStorefrontStripeTestCase(ModuleTestCase):
    'Test Web Shop Vue Storefront Stripe module'
    module = 'web_shop_vue_storefront_stripe'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            WebShopVueStorefrontStripeTestCase))
    return suite
