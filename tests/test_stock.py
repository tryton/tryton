#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import doctest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from functools import partial
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.backend.sqlite.database import Database as SQLiteDatabase
from trytond.transaction import Transaction


class StockTestCase(unittest.TestCase):
    '''
    Test Stock module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock')
        self.product = POOL.get('product.product')
        self.category = POOL.get('product.category')
        self.uom = POOL.get('product.uom')
        self.location = POOL.get('stock.location')
        self.move = POOL.get('stock.move')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.period = POOL.get('stock.period')
        self.cache = POOL.get('stock.period.cache')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('stock')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010move_internal_quantity(self):
        '''
        Test Move.internal_quantity.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            category_id = self.category.create({
                'name': 'Test Move.internal_quantity',
                })
            kg_id, = self.uom.search([('name', '=', 'Kilogram')])
            g_id, = self.uom.search([('name', '=', 'Gram')])
            product_id = self.product.create({
                'name': 'Test Move.internal_quantity',
                'type': 'goods',
                'list_price': Decimal(0),
                'cost_price': Decimal(0),
                'category': category_id,
                'cost_price_method': 'fixed',
                'default_uom': kg_id,
                })
            supplier_id, = self.location.search([('code', '=', 'SUP')])
            storage_id, = self.location.search([('code', '=', 'STO')])
            company_id, = self.company.search([('name', '=', 'B2CK')])
            currency_id = self.company.read(company_id,
                    ['currency'])['currency']
            self.user.write(USER, {
                'main_company': company_id,
                'company': company_id,
                })

            tests = [
                (kg_id, 10, 10),
                (g_id, 100, 0.1),
                (g_id, 1, 0), # rounded
            ]
            for uom_id, quantity, internal_quantity in tests:
                move_id = self.move.create({
                    'product': product_id,
                    'uom': uom_id,
                    'quantity': quantity,
                    'from_location': supplier_id,
                    'to_location': storage_id,
                    'company': company_id,
                    'unit_price': Decimal('1'),
                    'currency': currency_id,
                    })
                self.assertEqual(self.move.read(move_id,
                    ['internal_quantity'])['internal_quantity'],
                    internal_quantity)

                for uom_id, quantity, internal_quantity in tests:
                    self.move.write(move_id, {
                        'uom': uom_id,
                        'quantity': quantity,
                        })
                    self.assertEqual(self.move.read(move_id,
                        ['internal_quantity'])['internal_quantity'],
                        internal_quantity)

    def test0020products_by_location(self):
        '''
        Test products_by_location.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category_id = self.category.create({
                'name': 'Test products_by_location',
                })
            kg_id, = self.uom.search([('name', '=', 'Kilogram')])
            g_id, = self.uom.search([('name', '=', 'Gram')])
            product_id = self.product.create({
                'name': 'Test products_by_location',
                'type': 'goods',
                'list_price': Decimal(0),
                'cost_price': Decimal(0),
                'category': category_id,
                'cost_price_method': 'fixed',
                'default_uom': kg_id,
                })
            supplier_id, = self.location.search([('code', '=', 'SUP')])
            customer_id, = self.location.search([('code', '=', 'CUS')])
            storage_id, = self.location.search([('code', '=', 'STO')])
            company_id, = self.company.search([('name', '=', 'B2CK')])
            currency_id = self.company.read(company_id,
                    ['currency'])['currency']
            self.user.write(USER, {
                'main_company': company_id,
                'company': company_id,
                })

            today = datetime.date.today()

            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 5,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-5),
                'effective_date': today + relativedelta(days=-5),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 1,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-4),
                'state': 'draft',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 1,
                'from_location': storage_id,
                'to_location': customer_id,
                'planned_date': today,
                'effective_date': today,
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 1,
                'from_location': storage_id,
                'to_location': customer_id,
                'planned_date': today,
                'state': 'draft',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 2,
                'from_location': storage_id,
                'to_location': customer_id,
                'planned_date': today + relativedelta(days=5),
                'state': 'draft',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': kg_id,
                'quantity': 5,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=7),
                'state': 'draft',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })

            products_by_location = partial(self.product.products_by_location,
                    [storage_id], [product_id])
            products_by_location_zero = partial(
                    self.product.products_by_location,
                    [storage_id], [product_id], skip_zero=False)

            tests = [
                ({'stock_date_end': today + relativedelta(days=-6),
                }, 0),
                ({'stock_date_end': today + relativedelta(days=-5),
                }, 5),
                ({'stock_date_end': today + relativedelta(days=-4),
                }, 5),
                ({'stock_date_end': today + relativedelta(days=-3),
                }, 5),
                ({'stock_date_end': today,
                }, 4),
                ({'stock_date_end': today + relativedelta(days=1),
                }, 3),
                ({'stock_date_end': today + relativedelta(days=5),
                }, 1),
                ({'stock_date_end': today + relativedelta(days=6),
                }, 1),
                ({'stock_date_end': today + relativedelta(days=7),
                }, 6),
                ({'stock_date_end': today + relativedelta(days=8),
                }, 6),
                ({'stock_date_end': False,
                }, 6),
                ({'stock_date_end': today + relativedelta(days=-6),
                'forecast': True,
                }, 0),
                ({'stock_date_end': today + relativedelta(days=-5),
                'forecast': True,
                }, 5),
                ({'stock_date_end': today + relativedelta(days=-4),
                'forecast': True,
                }, 5),
                ({'stock_date_end': today + relativedelta(days=-3),
                'forecast': True,
                }, 5),
                ({'stock_date_end': today,
                'forecast': True,
                }, 3),
                ({'stock_date_end': today + relativedelta(days=1),
                'forecast': True,
                }, 3),
                ({'stock_date_end': today + relativedelta(days=5),
                'forecast': True,
                }, 1),
                ({'stock_date_end': today + relativedelta(days=6),
                'forecast': True,
                }, 1),
                ({'stock_date_end': today + relativedelta(days=7),
                'forecast': True,
                }, 6),
                ({'stock_date_end': False,
                'forecast': True,
                }, 6),
            ]

            def test_products_by_location():
                for context, quantity in tests:
                    with transaction.set_context(context):
                        if not quantity:
                            self.assertEqual(products_by_location(), {})
                            self.assertEqual(products_by_location_zero(),
                                    {(storage_id, product_id): quantity})
                        else:
                            self.assertEqual(products_by_location(),
                                    {(storage_id, product_id): quantity})

            test_products_by_location()

            periods = [
                today + relativedelta(days=-6),
                today + relativedelta(days=-5),
                today + relativedelta(days=-4),
                today + relativedelta(days=-3),
                today + relativedelta(days=-2),
            ]

            self.move.create({
                'product': product_id,
                'uom': g_id,
                'quantity': 1,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-5),
                'effective_date': today + relativedelta(days=-5),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            # Nothing should change when adding a small quantity
            test_products_by_location()

            for period_date in periods:
                period_id = self.period.create({
                    'date': period_date,
                    'company': company_id,
                })
                self.period.button_close([period_id])
                test_products_by_location()

    def test0030period(self):
        '''
        Test period.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            category_id = self.category.create({
                'name': 'Test period',
                })
            unit_id, = self.uom.search([('name', '=', 'Unit')])
            product_id = self.product.create({
                'name': 'Test period',
                'type': 'goods',
                'category': category_id,
                'cost_price_method': 'fixed',
                'default_uom': unit_id,
                'list_price': Decimal(0),
                'cost_price': Decimal(0),
                })
            supplier_id, = self.location.search([('code', '=', 'SUP')])
            customer_id, = self.location.search([('code', '=', 'CUS')])
            storage_id, = self.location.search([('code', '=', 'STO')])
            company_id, = self.company.search([('name', '=', 'B2CK')])
            currency_id = self.company.read(company_id,
                    ['currency'])['currency']
            self.user.write(USER, {
                'main_company': company_id,
                'company': company_id,
                })

            today = datetime.date.today()

            self.move.create({
                'product': product_id,
                'uom': unit_id,
                'quantity': 10,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-5),
                'effective_date': today + relativedelta(days=-5),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': unit_id,
                'quantity': 15,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-4),
                'effective_date': today + relativedelta(days=-4),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })
            self.move.create({
                'product': product_id,
                'uom': unit_id,
                'quantity': 5,
                'from_location': storage_id,
                'to_location': customer_id,
                'planned_date': today + relativedelta(days=-3),
                'effective_date': today + relativedelta(days=-3),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })

            tests = [
                (-5, {
                    supplier_id: -10,
                    storage_id: 10,
                }),
                (-3, {
                    supplier_id: -25,
                    storage_id: 20,
                    customer_id: 5,
                })
            ]

            for days, quantities in tests:
                period_id = self.period.create({
                    'date': today + relativedelta(days=days),
                    'company': company_id,
                })
                self.period.button_close([period_id])

                period = self.period.read(period_id, ['state', 'caches'])
                self.assertEqual(period['state'], 'closed')

                cache_ids = period['caches']
                caches = self.cache.read(cache_ids,
                    ['location', 'product', 'internal_quantity'])
                for cache in caches:
                    location_id = cache['location']
                    self.assertEqual(cache['product'], product_id)
                    self.assertEqual(cache['internal_quantity'],
                        quantities[location_id])

            # Test check_period_closed
            self.move.create({
                'product': product_id,
                'uom': unit_id,
                'quantity': 10,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today,
                'effective_date': today,
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })

            self.assertRaises(Exception, self.move.create, {
                'product': product_id,
                'uom': unit_id,
                'quantity': 10,
                'from_location': supplier_id,
                'to_location': storage_id,
                'planned_date': today + relativedelta(days=-5),
                'effective_date': today + relativedelta(days=-5),
                'state': 'done',
                'company': company_id,
                'unit_price': Decimal('1'),
                'currency': currency_id,
                })

            # Test close period check
            period_id = self.period.create({
                'date': today,
                'company': company_id,
            })
            self.assertRaises(Exception, self.period.button_close, [period_id])

            period_id = self.period.create({
                'date': today + relativedelta(days=1),
                'company': company_id,
            })
            self.assertRaises(Exception, self.period.button_close, [period_id])


def doctest_dropdb(test):
    '''
    Remove sqlite memory database
    '''
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(StockTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_shipment_out.rst',
        setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))

    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
