# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class SaleShipmentCostTestCase(ModuleTestCase):
    'Test Sale Shipment Cost module'
    module = 'sale_shipment_cost'
    extras = ['sale_promotion']


del ModuleTestCase
