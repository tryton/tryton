# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import MagicMock, Mock

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

    @with_transaction()
    def test_sale_incoterm_required(self):
        "Test incoterm required on sale"
        pool = Pool()
        Sale = pool.get('sale.sale')
        Country = pool.get('country.country')

        from_country = Mock(spec=Country)
        to_country = Mock(spec=Country)
        sale = Mock(spec=Sale)
        sale.warehouse.address.country = from_country
        sale.shipment_address.country = to_country
        type(sale)._incoterm_required = Sale._incoterm_required

        for from_europe, to_europe, result in [
                (False, False, True),
                (False, True, True),
                (True, False, True),
                (True, True, False),
                ]:
            from_country.is_member.return_value = from_europe
            to_country.is_member.return_value = to_europe
            with self.subTest(
                    from_europe=from_europe,
                    to_europe=to_europe):
                self.assertEqual(sale._incoterm_required, result)

    @with_transaction()
    def test_sale_incoterm_required_same_country(self):
        "Test incoterm required on sale with same country"
        pool = Pool()
        Sale = pool.get('sale.sale')
        Country = pool.get('country.country')

        country = Mock(spec=Country)
        sale = Mock(spec=Sale)
        sale.warehouse.address.country = country
        sale.shipment_address.country = country
        type(sale)._incoterm_required = Sale._incoterm_required

        for europe, result in [
                (False, False),
                (True, False),
                ]:
            country.is_member.return_value = europe
            with self.subTest(europe=europe):
                self.assertEqual(sale._incoterm_required, result)

    @with_transaction()
    def test_sale_incoterm_required_no_country(self):
        "Test incoterm required on sale without country"
        pool = Pool()
        Sale = pool.get('sale.sale')

        sale = Mock(spec=Sale)
        sale.warehouse.address.country = None
        sale.shipment_address.country = None
        type(sale)._incoterm_required = Sale._incoterm_required

        self.assertFalse(sale._incoterm_required)


del ModuleTestCase
