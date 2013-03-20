#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys
import os
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
        self.template = POOL.get('product.template')
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
            category, = self.category.create([{
                        'name': 'Test Move.internal_quantity',
                        }])
            kg, = self.uom.search([('name', '=', 'Kilogram')])
            g, = self.uom.search([('name', '=', 'Gram')])
            template, = self.template.create([{
                        'name': 'Test Move.internal_quantity',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'category': category.id,
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([('rec_name', '=', 'B2CK')])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            tests = [
                (kg, 10, 10),
                (g, 100, 0.1),
                (g, 1, 0),  # rounded
            ]
            for uom, quantity, internal_quantity in tests:
                move, = self.move.create([{
                            'product': product.id,
                            'uom': uom.id,
                            'quantity': quantity,
                            'from_location': supplier.id,
                            'to_location': storage.id,
                            'company': company.id,
                            'unit_price': Decimal('1'),
                            'currency': currency.id,
                            }])
                self.assertEqual(move.internal_quantity, internal_quantity)

                for uom, quantity, internal_quantity in tests:
                    self.move.write([move], {
                        'uom': uom.id,
                        'quantity': quantity,
                        })
                    self.assertEqual(move.internal_quantity, internal_quantity)

    def test0020products_by_location(self):
        '''
        Test products_by_location.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category, = self.category.create([{
                        'name': 'Test products_by_location',
                        }])
            kg, = self.uom.search([('name', '=', 'Kilogram')])
            g, = self.uom.search([('name', '=', 'Gram')])
            template, = self.template.create([{
                        'name': 'Test products_by_location',
                        'type': 'goods',
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        'category': category.id,
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            customer, = self.location.search([('code', '=', 'CUS')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([('rec_name', '=', 'B2CK')])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            today = datetime.date.today()

            moves = self.move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-5),
                        'effective_date': today + relativedelta(days=-5),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 1,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-4),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 1,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'planned_date': today,
                        'effective_date': today,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 1,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'planned_date': today,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 2,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'planned_date': today + relativedelta(days=5),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=7),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do([moves[0], moves[2]])

            products_by_location = partial(self.product.products_by_location,
                    [storage.id], [product.id])
            products_by_location_zero = partial(
                    self.product.products_by_location,
                    [storage.id], [product.id], skip_zero=False)

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
                                    {(storage.id, product.id): quantity})
                        else:
                            self.assertEqual(products_by_location(),
                                    {(storage.id, product.id): quantity})

            test_products_by_location()

            periods = [
                today + relativedelta(days=-6),
                today + relativedelta(days=-5),
                today + relativedelta(days=-4),
                today + relativedelta(days=-3),
                today + relativedelta(days=-2),
            ]

            moves = self.move.create([{
                        'product': product.id,
                        'uom': g.id,
                        'quantity': 1,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-5),
                        'effective_date': (today
                            + relativedelta(days=-5)),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do(moves)
            # Nothing should change when adding a small quantity
            test_products_by_location()

            for period_date in periods:
                period, = self.period.create([{
                            'date': period_date,
                            'company': company.id,
                            }])
                self.period.close([period])
                test_products_by_location()

        # Test with_childs
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company, = self.company.search([('rec_name', '=', 'B2CK')])
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test products_by_location',
                        'type': 'goods',
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])

            lost_found, = self.location.search([('type', '=', 'lost_found')])
            warehouse, = self.location.search([('type', '=', 'warehouse')])
            storage, = self.location.search([('code', '=', 'STO')])
            storage1, = self.location.create([{
                        'name': 'Storage 1',
                        'type': 'view',
                        'parent': storage.id,
                        }])
            storage2, = self.location.create([{
                        'name': 'Storage 1.1',
                        'type': 'view',
                        'parent': storage1.id,
                        }])
            storage3, = self.location.create([{
                        'name': 'Storage 2',
                        'type': 'view',
                        'parent': storage.id,
                        }])

            moves = self.move.create([{
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'planned_date': today,
                        'effective_date': today,
                        'company': company.id,
                        }])
            self.move.do(moves)

            products_by_location = self.product.products_by_location(
                [warehouse.id], [product.id], with_childs=True)
            self.assertEqual(products_by_location[(warehouse.id, product.id)],
                1)

    def test0030period(self):
        '''
        Test period.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            category, = self.category.create([{
                        'name': 'Test period',
                        }])
            unit, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test period',
                        'type': 'goods',
                        'category': category.id,
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            customer, = self.location.search([('code', '=', 'CUS')])
            storage, = self.location.search([('code', '=', 'STO')])
            company, = self.company.search([('rec_name', '=', 'B2CK')])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            today = datetime.date.today()

            moves = self.move.create([{
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-5),
                        'effective_date': today + relativedelta(days=-5),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 15,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-4),
                        'effective_date': today + relativedelta(days=-4),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 5,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'planned_date': today + relativedelta(days=-3),
                        'effective_date': today + relativedelta(days=-3),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do(moves)

            tests = [
                (-5, {
                    supplier.id: -10,
                    storage.id: 10,
                }),
                (-3, {
                    supplier.id: -25,
                    storage.id: 20,
                    customer.id: 5,
                })
            ]

            for days, quantities in tests:
                period, = self.period.create([{
                            'date': today + relativedelta(days=days),
                            'company': company.id,
                            }])
                self.period.close([period])

                self.assertEqual(period.state, 'closed')

                caches = period.caches
                for cache in caches:
                    self.assertEqual(cache.product, product)
                    self.assertEqual(cache.internal_quantity,
                        quantities[cache.location.id])

            # Test check_period_closed
            moves = self.move.create([{
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today,
                        'effective_date': today,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do(moves)

            self.assertRaises(Exception, self.move.create, [{
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': today + relativedelta(days=-5),
                        'effective_date': today + relativedelta(days=-5),
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])

            # Test close period check
            period, = self.period.create([{
                        'date': today,
                        'company': company.id,
                        }])
            self.assertRaises(Exception, self.period.close, [period])

            period, = self.period.create([{
                        'date': today + relativedelta(days=1),
                        'company': company.id,
                        }])
            self.assertRaises(Exception, self.period.close, [period])


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
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_average_cost_price.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
