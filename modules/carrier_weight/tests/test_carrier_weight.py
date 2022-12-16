# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from trytond.modules.currency.tests import create_currency


class CarrierWeightTestCase(ModuleTestCase):
    'Test CarrierWeight module'
    module = 'carrier_weight'
    extras = ['purchase_shipment_cost', 'sale_shipment_cost']

    @with_transaction()
    def test_compute_weight_price(self):
        'Test compute_weight_price'
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
                    'list_price': Decimal(0),
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
        for i, weight in enumerate(range(0, 100, 20)):
            WeightPriceList.create([{
                        'carrier': carrier.id,
                        'weight': weight,
                        'price': Decimal(i),
                        }])
        self.assertEqual(
            carrier.compute_weight_price(0), Decimal(0))
        for weight, price in [
                (1, Decimal(0)),
                (10, Decimal(0)),
                (20, Decimal(0)),
                (21, Decimal(1)),
                (80, Decimal(3)),
                (81, Decimal(4)),
                (100, Decimal(4)),
                ]:
            self.assertEqual(carrier.compute_weight_price(weight), price)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CarrierWeightTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_carrier_weight.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
