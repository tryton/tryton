# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class StockPackageShippingMyglsTestCase(ModuleTestCase):
    'Test Stock Package Shipping Mygls module'
    module = 'stock_package_shipping_mygls'


del ModuleTestCase
