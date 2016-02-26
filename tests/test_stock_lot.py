# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class StockLotTestCase(ModuleTestCase):
    'Test Stock Lot module'
    module = 'stock_lot'

    @with_transaction()
    def test_products_by_location(self):
        'Test products_by_location'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')

        kg, = Uom.search([('name', '=', 'Kilogram')])
        g, = Uom.search([('name', '=', 'Gram')])
        template, = Template.create([{
                    'name': 'Test products_by_location',
                    'type': 'goods',
                    'list_price': Decimal(0),
                    'cost_price': Decimal(0),
                    'cost_price_method': 'fixed',
                    'default_uom': kg.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        supplier, = Location.search([('code', '=', 'SUP')])
        customer, = Location.search([('code', '=', 'CUS')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        currency = company.currency
        with set_company(company):
            lot1, lot2 = Lot.create([{
                        'number': '1',
                        'product': product.id,
                        }, {
                        'number': '2',
                        'product': product.id,
                        }])

            moves = Move.create([{
                        'product': product.id,
                        'lot': lot1.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': lot2.id,
                        'uom': kg.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': lot2.id,
                        'uom': kg.id,
                        'quantity': 2,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': None,
                        'uom': kg.id,
                        'quantity': 3,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            Move.do(moves)

            self.assertEqual(Product.products_by_location([storage.id],
                    [product.id]), {
                    (storage.id, product.id): 16,
                    })
            self.assertEqual(Product.products_by_location([storage.id],
                    [product.id], grouping=('product', 'lot')), {
                    (storage.id, product.id, lot1.id): 5,
                    (storage.id, product.id, lot2.id): 8,
                    (storage.id, product.id, None): 3,
                    })
            with Transaction().set_context(locations=[storage.id]):
                self.assertEqual(lot1.quantity, 5)
                self.assertEqual(lot2.quantity, 8)

    @with_transaction()
    def test_period(self):
        'Test period'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')
        Period = pool.get('stock.period')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test period',
                    'type': 'goods',
                    'cost_price_method': 'fixed',
                    'default_uom': unit.id,
                    'list_price': Decimal(0),
                    'cost_price': Decimal(0),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        currency = company.currency
        with set_company(company):
            lot1, lot2 = Lot.create([{
                        'number': '1',
                        'product': product.id,
                        }, {
                        'number': '2',
                        'product': product.id,
                        }])

            today = datetime.date.today()

            moves = Move.create([{
                        'product': product.id,
                        'lot': lot1.id,
                        'uom': unit.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': lot2.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': None,
                        'uom': unit.id,
                        'quantity': 3,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today - relativedelta(days=1),
                        'effective_date': today - relativedelta(days=1),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            Move.do(moves)

            period, = Period.create([{
                        'date': today - relativedelta(days=1),
                        'company': company.id,
                        }])
            Period.close([period])
            self.assertEqual(period.state, 'closed')

            quantities = {
                supplier: -18,
                storage: 18,
                }
            for cache in period.caches:
                self.assertEqual(cache.product, product)
                self.assertEqual(cache.internal_quantity,
                    quantities[cache.location])

            quantities = {
                (supplier, lot1): -5,
                (storage, lot1): 5,
                (supplier, lot2): -10,
                (storage, lot2): 10,
                (supplier, None): -3,
                (storage, None): 3,
                }
            for lot_cache in period.lot_caches:
                self.assertEqual(lot_cache.product, product)
                self.assertEqual(lot_cache.internal_quantity,
                    quantities[(lot_cache.location, lot_cache.lot)])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockLotTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_lot_shipment_out.rst',
        setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
