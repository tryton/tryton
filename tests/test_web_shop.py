# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest


from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class WebShopTestCase(ModuleTestCase):
    'Test Web Shop module'
    module = 'web_shop'
    extras = ['product_attribute']


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            WebShopTestCase))
    return suite
