# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class CarrierCarriageTestCase(ModuleTestCase):
    "Test Carrier Carriage module"
    module = 'carrier_carriage'
    extras = ['incoterm', 'purchase_shipment_cost', 'sale_shipment_cost']


del ModuleTestCase
