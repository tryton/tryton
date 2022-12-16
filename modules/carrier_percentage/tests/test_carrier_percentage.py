# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from trytond.modules.currency.tests import create_currency


class CarrierPercentageTestCase(ModuleTestCase):
    'Test CarrierPercentage module'
    module = 'carrier_percentage'

    @with_transaction()
    def test_compute_percentage(self):
        'Test compute_percentage'
        pool = Pool()
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Carrier = pool.get('carrier')

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
                    'cost_price': Decimal(0),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        currency = create_currency('cu1')
        carrier, = Carrier.create([{
                    'party': party.id,
                    'carrier_product': product.id,
                    'carrier_cost_method': 'percentage',
                    'percentage': Decimal(15),
                    }])
        for amount, price in [
                (Decimal(0), Decimal(0)),
                (Decimal(100), Decimal('15.00')),
                (Decimal(150), Decimal('22.50')),
                ]:
            self.assertEqual(
                carrier.compute_percentage(amount, currency.id),
                (price, currency.id))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CarrierPercentageTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_carrier_percentage_with_purchase_shipment_cost.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
