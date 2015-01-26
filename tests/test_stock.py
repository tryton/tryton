# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from functools import partial
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends, test_menu_action
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.transaction import Transaction
from trytond.exceptions import UserWarning


class StockTestCase(unittest.TestCase):
    'Test Stock module'

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
        'Test views'
        test_view('stock')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0007menu_actions(self):
        'Test menu actions'
        test_menu_action('stock')

    def test0010move_internal_quantity(self):
        'Test Move.internal_quantity'
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
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })

            tests = [
                (kg, 10, 10, 0),
                (g, 100, 0.1, 1),
                (g, 1, 0, 0),  # rounded
                (kg, 35.23, 35.23, 2),  # check infinite loop
            ]
            for uom, quantity, internal_quantity, ndigits in tests:
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
                self.assertEqual(round(move.internal_quantity, ndigits),
                    internal_quantity)

                for uom, quantity, internal_quantity, ndigits in tests:
                    self.move.write([move], {
                        'uom': uom.id,
                        'quantity': quantity,
                        })
                    self.assertEqual(round(move.internal_quantity, ndigits),
                        internal_quantity)

    def test0020products_by_location(self):
        'Test products_by_location'
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
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
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

            def tests_product_quantity(context, quantity):
                with transaction.set_context(locations=[storage.id]):
                    product_reloaded = self.product(product.id)
                    if (not context.get('stock_date_end')
                            or context['stock_date_end'] > today
                            or context.get('forecast')):
                        self.assertEqual(product_reloaded.forecast_quantity,
                            quantity)
                    else:
                        self.assertEqual(product_reloaded.quantity, quantity)

            def tests_product_search_quantity(context, quantity):
                with transaction.set_context(locations=[storage.id]):
                    if (not context.get('stock_date_end')
                            or context['stock_date_end'] > today
                            or context.get('forecast')):
                        fname = 'forecast_quantity'
                    else:
                        fname = 'quantity'
                    found_products = self.product.search([
                            (fname, '=', quantity),
                            ])
                    self.assertIn(product, found_products)

                    found_products = self.product.search([
                            (fname, '!=', quantity),
                            ])
                    self.assertNotIn(product, found_products)

                    found_products = self.product.search([
                            (fname, 'in', (quantity, quantity + 1)),
                            ])
                    self.assertIn(product, found_products)

                    found_products = self.product.search([
                            (fname, 'not in', (quantity, quantity + 1)),
                            ])
                    self.assertNotIn(product, found_products)

                    found_products = self.product.search([
                            (fname, '<', quantity),
                            ])
                    self.assertNotIn(product, found_products)
                    found_products = self.product.search([
                            (fname, '<', quantity + 1),
                            ])
                    self.assertIn(product, found_products)

                    found_products = self.product.search([
                            (fname, '>', quantity),
                            ])
                    self.assertNotIn(product, found_products)
                    found_products = self.product.search([
                            (fname, '>', quantity - 1),
                            ])
                    self.assertIn(product, found_products)

                    found_products = self.product.search([
                            (fname, '>=', quantity),
                            ])
                    self.assertIn(product, found_products)

                    found_products = self.product.search([
                            (fname, '<=', quantity),
                            ])
                    self.assertIn(product, found_products)

            def test_products_by_location():
                for context, quantity in tests:
                    with transaction.set_context(context):
                        if not quantity:
                            self.assertEqual(products_by_location(), {})
                        else:
                            self.assertEqual(products_by_location(),
                                    {(storage.id, product.id): quantity})
                            tests_product_quantity(context, quantity)
                            tests_product_search_quantity(context, quantity)

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

        # Test with_childs and stock_skip_warehouse
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
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
            input_, = self.location.search([('code', '=', 'IN')])
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
                        }, {
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 1,
                        'from_location': input_.id,
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

            with Transaction().set_context(stock_skip_warehouse=True):
                products_by_location = self.product.products_by_location(
                    [warehouse.id], [product.id], with_childs=True)
                products_by_location_all = self.product.products_by_location(
                    [warehouse.id], None, with_childs=True)
            self.assertEqual(products_by_location[(warehouse.id, product.id)],
                2)
            self.assertEqual(
                products_by_location_all[(warehouse.id, product.id)], 2)

    def test0030period(self):
        'Test period'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
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
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
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
            self.move.create([{
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 3,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'planned_date': None,
                        'effective_date': None,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])

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

            products_by_location = partial(self.product.products_by_location,
                [storage.id], [product.id])

            tests_pbl = [
                ({'stock_date_end': today + relativedelta(days=-6)}, 0),
                ({'stock_date_end': today + relativedelta(days=-5)}, 10),
                ({'stock_date_end': today + relativedelta(days=-4)}, 25),
                ({'stock_date_end': today + relativedelta(days=-3)}, 20),
                ({'stock_date_end': today + relativedelta(days=-2)}, 20),
                ({'stock_date_end': today}, 20),
                ({'stock_date_end': datetime.date.max}, 23),
                ]

            def test_products_by_location():
                for context, quantity in tests_pbl:
                    with transaction.set_context(context):
                        if not quantity:
                            self.assertEqual(products_by_location(), {})
                        else:
                            self.assertEqual(products_by_location(),
                                    {(storage.id, product.id): quantity})

            test_products_by_location()
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

                test_products_by_location()

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

    def test0040check_origin(self):
        'Test Move check_origin'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            uom, = self.uom.search([('name', '=', 'Unit')])
            template, = self.template.create([{
                        'name': 'Test Move.check_origin',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': uom.id,
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            storage, = self.location.search([('code', '=', 'STO')])
            customer, = self.location.search([('code', '=', 'CUS')])
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])

            moves = self.move.create([{
                        'product': product.id,
                        'uom': uom.id,
                        'quantity': 1,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal(1),
                        'currency': company.currency.id,
                        }])

            self.move.check_origin(moves, set())
            self.move.check_origin(moves, {'supplier'})
            self.assertRaises(UserWarning, self.move.check_origin, moves,
                {'customer'})


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(StockTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_shipment_out.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_average_cost_price.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_inventory.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_stock_shipment_internal.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_stock_reporting.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
