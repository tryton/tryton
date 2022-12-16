#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class PurchaseShipmentCostTestCase(ModuleTestCase):
    'Test Purchase Shipment Cost module'
    module = 'purchase_shipment_cost'


del ModuleTestCase
