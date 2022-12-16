#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends, doctest_dropdb
from trytond.transaction import Transaction


class StockLotTestCase(unittest.TestCase):
    'Test Stock Lot module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_lot')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.uom = POOL.get('product.uom')
        self.lot = POOL.get('stock.lot')
        self.location = POOL.get('stock.location')
        self.move = POOL.get('stock.move')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.period = POOL.get('stock.period')
        self.cache = POOL.get('stock.period.cache')

    def test0005views(self):
        'Test views'
        test_view('stock_lot')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010products_by_location(self):
        'Test products_by_location'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            kg, = self.uom.search([('name', '=', 'Kilogram')])
            g, = self.uom.search([('name', '=', 'Gram')])
            template, = self.template.create([{
                        'name': 'Test products_by_location',
                        'type': 'goods',
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            customer, = self.location.search([('code', '=', 'CUS')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            lot1, lot2 = self.lot.create([{
                        'number': '1',
                        'product': product.id,
                        }, {
                        'number': '2',
                        'product': product.id,
                        }])

            moves = self.move.create([{
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
            self.move.do(moves)

            self.assertEqual(self.product.products_by_location([storage.id],
                    [product.id]), {
                    (storage.id, product.id): 16,
                    })
            self.assertEqual(self.product.products_by_location([storage.id],
                    [product.id], grouping=('product', 'lot')), {
                    (storage.id, product.id, lot1.id): 5,
                    (storage.id, product.id, lot2.id): 8,
                    (storage.id, product.id, None): 3,
                    })
            with Transaction().set_context(locations=[storage.id]):
                self.assertEqual(lot1.quantity, 5)
                self.assertEqual(lot2.quantity, 8)

    def test0020period(self):
        'Test period'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            lot1, lot2 = self.lot.create([{
                        'number': '1',
                        'product': product.id,
                        }, {
                        'number': '2',
                        'product': product.id,
                        }])

            today = datetime.date.today()

            moves = self.move.create([{
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
            self.move.do(moves)

            period, = self.period.create([{
                        'date': today - relativedelta(days=1),
                        'company': company.id,
                        }])
            self.period.close([period])
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
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockLotTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_lot_shipment_out.rst',
        setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
