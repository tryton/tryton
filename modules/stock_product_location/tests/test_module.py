# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class StockProductLocationTestCase(ModuleTestCase):
    'Test StockProductLocation module'
    module = 'stock_product_location'
    extras = ['production']


del ModuleTestCase
