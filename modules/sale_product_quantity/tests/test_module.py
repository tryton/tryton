# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class SaleProductQuantityTestCase(ModuleTestCase):
    'Test Sale Product Quantity module'
    module = 'sale_product_quantity'
    extras = ['sale_point']


del ModuleTestCase
