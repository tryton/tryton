# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import CompanyTestMixin
from trytond.modules.currency.tests import create_currency
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class CarrierWeightTestCase(CompanyTestMixin, ModuleTestCase):
    'Test CarrierWeight module'
    module = 'carrier_weight'
    extras = [
        'purchase_shipment_cost', 'sale_shipment_cost', 'stock_shipment_cost']

    def create_carrier(self):
        pool = Pool()
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Carrier = pool.get('carrier')
        WeightPriceList = pool.get('carrier.weight_price_list')

        party, = Party.create([{
                    'name': 'Carrier',
                    }])
        uom, = Uom.search([
                ('name', '=', 'Unit'),
                ])
        template, = Template.create([{
                    'name': 'Carrier',
                    'default_uom': uom.id,
                    'type': 'service',
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        weight_uom, = Uom.search([
                ('name', '=', 'Kilogram'),
                ])
        currency = create_currency('cu1')
        carrier, = Carrier.create([{
                    'party': party.id,
                    'carrier_product': product.id,
                    'carrier_cost_method': 'weight',
                    'weight_uom': weight_uom.id,
                    'weight_currency': currency.id,
                    }])
        for i, weight in enumerate(range(0, 100, 20), 1):
            WeightPriceList.create([{
                        'carrier': carrier.id,
                        'weight': weight,
                        'price': Decimal(i),
                        }])
        return carrier

    @with_transaction()
    def test_compute_weight_price(self):
        'Test compute_weight_price'
        carrier = self.create_carrier()

        for weight, price in [
                (-1, Decimal(0)),
                (0, Decimal(1)),
                (1, Decimal(1)),
                (10, Decimal(1)),
                (20, Decimal(1)),
                (21, Decimal(2)),
                (80, Decimal(4)),
                (81, Decimal(5)),
                (100, Decimal(5)),
                ]:
            with self.subTest(weight=weight):
                self.assertEqual(carrier.compute_weight_price(weight), price)

    @with_transaction()
    def test_get_weight_price(self):
        "Test get_weight_price"
        transaction = Transaction()
        carrier = self.create_carrier()

        for weights, price in [
                ([], Decimal(1)),
                ([0], Decimal(1)),
                ([0, 0], Decimal(2)),
                ([21], Decimal(2)),
                ([10, 21], Decimal(3)),
                ([0, 21], Decimal(3)),
                ]:
            with self.subTest(weights=weights):
                with transaction.set_context(weights=weights):
                    self.assertEqual(
                        carrier.get_sale_price(),
                        (price, carrier.weight_currency.id))
                    self.assertEqual(
                        carrier.get_purchase_price(),
                        (price, carrier.weight_currency.id))


del ModuleTestCase
