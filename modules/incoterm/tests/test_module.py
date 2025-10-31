# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import MagicMock

from trytond.modules.company.tests import CompanyTestMixin
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class IncotermTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Incoterm module'
    module = 'incoterm'
    extras = [
        'carrier', 'company', 'purchase', 'purchase_request_quotation',
        'sale', 'sale_shipment_cost', 'sale_opportunity',
        'sale_shipment_grouping', 'stock', 'account_invoice',
        'account_invoice_stock', 'web_shop']

    @with_transaction()
    def test_shipment_grouping(self):
        "Test fields to group shipment"
        pool = Pool()
        Sale = pool.get('sale.sale')
        ShipmentOut = pool.get('stock.shipment.out')

        sale = Sale()
        shipment = MagicMock(spec=ShipmentOut)

        fields = sale._get_shipment_grouping_fields(shipment)

        self.assertLessEqual({'incoterm', 'incoterm_location'}, fields)
        self.assertLessEqual(fields, ShipmentOut._fields.keys())


del ModuleTestCase
