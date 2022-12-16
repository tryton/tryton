# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class CarrierSubdivisionTestCase(ModuleTestCase):
    "Test Carrier Subdivision module"
    module = 'carrier_subdivision'
    extras = ['carrier_carriage', 'sale_shipment_cost']


del ModuleTestCase
