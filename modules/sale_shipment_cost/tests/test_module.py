# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import MagicMock

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class SaleShipmentCostTestCase(ModuleTestCase):
    'Test Sale Shipment Cost module'
    module = 'sale_shipment_cost'
    extras = ['sale_promotion', 'sale_shipment_grouping']

    @with_transaction()
    def test_shipment_grouping(self):
        "Test fields to group shipment"
        pool = Pool()
        Sale = pool.get('sale.sale')
        ShipmentOut = pool.get('stock.shipment.out')

        sale = Sale()
        shipment = MagicMock(spec=ShipmentOut)

        fields = sale._get_shipment_grouping_fields(shipment)

        self.assertLessEqual({'cost_method', 'carrier'}, fields)
        self.assertLessEqual(fields, ShipmentOut._fields.keys())


del ModuleTestCase
