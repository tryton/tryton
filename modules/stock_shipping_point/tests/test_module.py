# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class StockShippingPointTestCase(ModuleTestCase):
    "Test Stock Shipping Point module"
    module = 'stock_shipping_point'
    extras = ['product_classification', 'stock_shipment_measurements']


del ModuleTestCase
