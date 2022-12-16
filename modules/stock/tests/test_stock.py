# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from functools import partial
from collections import defaultdict

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.transaction import Transaction
from trytond.exceptions import UserWarning
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class StockTestCase(ModuleTestCase):
    'Test Stock module'
    module = 'stock'
    longMessage = True

    @with_transaction()
    def test_move_internal_quantity(self):
        'Test Move.internal_quantity'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        kg, = Uom.search([('name', '=', 'Kilogram')])
        g, = Uom.search([('name', '=', 'Gram')])
        template, = Template.create([{
                    'name': 'Test Move.internal_quantity',
                    'type': 'goods',
                    'list_price': Decimal(1),
                    'cost_price': Decimal(0),
                    'cost_price_method': 'fixed',
                    'default_uom': kg.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        currency = company.currency
        with set_company(company):
            tests = [
                (kg, 10, 10, 0),
                (g, 100, 0.1, 1),
                (g, 1, 0, 0),  # rounded
                (kg, 35.23, 35.23, 2),  # check infinite loop
            ]
            for uom, quantity, internal_quantity, ndigits in tests:
                move, = Move.create([{
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
                    Move.write([move], {
                        'uom': uom.id,
                        'quantity': quantity,
                        })
                    self.assertEqual(round(move.internal_quantity, ndigits),
                        internal_quantity)

    @with_transaction()
    def test_products_by_location(self):
        'Test products_by_location'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Period = pool.get('stock.period')
        transaction = Transaction()

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
            today = datetime.date.today()

            moves = Move.create([{
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
            Move.do([moves[0], moves[2]])

            products_by_location = partial(Product.products_by_location,
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
                    product_reloaded = Product(product.id)
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
                    found_products = Product.search([
                            (fname, '=', quantity),
                            ])
                    self.assertIn(product, found_products)

                    found_products = Product.search([
                            (fname, '!=', quantity),
                            ])
                    self.assertNotIn(product, found_products)

                    found_products = Product.search([
                            (fname, 'in', (quantity, quantity + 1)),
                            ])
                    self.assertIn(product, found_products)

                    found_products = Product.search([
                            (fname, 'not in', (quantity, quantity + 1)),
                            ])
                    self.assertNotIn(product, found_products)

                    found_products = Product.search([
                            (fname, '<', quantity),
                            ])
                    self.assertNotIn(product, found_products)
                    found_products = Product.search([
                            (fname, '<', quantity + 1),
                            ])
                    self.assertIn(product, found_products)

                    found_products = Product.search([
                            (fname, '>', quantity),
                            ])
                    self.assertNotIn(product, found_products)
                    found_products = Product.search([
                            (fname, '>', quantity - 1),
                            ])
                    self.assertIn(product, found_products)

                    found_products = Product.search([
                            (fname, '>=', quantity),
                            ])
                    self.assertIn(product, found_products)

                    found_products = Product.search([
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

            moves = Move.create([{
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
            Move.do(moves)
            # Nothing should change when adding a small quantity
            test_products_by_location()

            for period_date in periods:
                period, = Period.create([{
                            'date': period_date,
                            'company': company.id,
                            }])
                Period.close([period])
                test_products_by_location()

    @with_transaction()
    def test_products_by_location_with_childs(self):
        'Test products_by_location with_childs and stock_skip_warehouse'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test products_by_location',
                    'type': 'goods',
                    'list_price': Decimal(0),
                    'cost_price': Decimal(0),
                    'cost_price_method': 'fixed',
                    'default_uom': unit.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        lost_found, = Location.search([('type', '=', 'lost_found')])
        warehouse, = Location.search([('type', '=', 'warehouse')])
        storage, = Location.search([('code', '=', 'STO')])
        input_, = Location.search([('code', '=', 'IN')])
        storage1, = Location.create([{
                    'name': 'Storage 1',
                    'type': 'view',
                    'parent': storage.id,
                    }])
        storage2, = Location.create([{
                    'name': 'Storage 1.1',
                    'type': 'view',
                    'parent': storage1.id,
                    }])
        storage3, = Location.create([{
                    'name': 'Storage 2',
                    'type': 'view',
                    'parent': storage.id,
                    }])
        company = create_company()
        with set_company(company):
            today = datetime.date.today()

            moves = Move.create([{
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
            Move.do(moves)

            products_by_location = Product.products_by_location(
                [warehouse.id], [product.id], with_childs=True)
            self.assertEqual(products_by_location[(warehouse.id, product.id)],
                1)
            products_by_location = Product.products_by_location(
                [warehouse.id, storage.id], [product.id], with_childs=True)
            self.assertEqual(
                products_by_location[(warehouse.id, product.id)], 1)
            self.assertEqual(products_by_location[(storage.id, product.id)], 2)

            with Transaction().set_context(stock_skip_warehouse=True):
                products_by_location = Product.products_by_location(
                    [warehouse.id], [product.id], with_childs=True)
                products_by_location_all = Product.products_by_location(
                    [warehouse.id], None, with_childs=True)
            self.assertEqual(
                products_by_location[(warehouse.id, product.id)], 2)
            self.assertEqual(
                products_by_location_all[(warehouse.id, product.id)], 2)

    @with_transaction()
    def test_period(self):
        'Test period'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Period = pool.get('stock.period')
        transaction = Transaction()

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
        customer, = Location.search([('code', '=', 'CUS')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        currency = company.currency
        with set_company(company):
            today = datetime.date.today()

            moves = Move.create([{
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
            Move.do(moves)
            Move.create([{
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

            products_by_location = partial(Product.products_by_location,
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
                period, = Period.create([{
                            'date': today + relativedelta(days=days),
                            'company': company.id,
                            }])
                Period.close([period])

                self.assertEqual(period.state, 'closed')

                caches = period.caches
                for cache in caches:
                    self.assertEqual(cache.product, product)
                    self.assertEqual(cache.internal_quantity,
                        quantities[cache.location.id])

                test_products_by_location()

            # Test check_period_closed
            moves = Move.create([{
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
            Move.do(moves)

            self.assertRaises(Exception, Move.create, [{
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
            period, = Period.create([{
                        'date': today,
                        'company': company.id,
                        }])
            self.assertRaises(Exception, Period.close, [period])

            period, = Period.create([{
                        'date': today + relativedelta(days=1),
                        'company': company.id,
                        }])
            self.assertRaises(Exception, Period.close, [period])

    @with_transaction()
    def test_check_origin(self):
        'Test Move check_origin'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        uom, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test Move.check_origin',
                    'type': 'goods',
                    'list_price': Decimal(1),
                    'cost_price': Decimal(0),
                    'cost_price_method': 'fixed',
                    'default_uom': uom.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        storage, = Location.search([('code', '=', 'STO')])
        customer, = Location.search([('code', '=', 'CUS')])
        company = create_company()
        with set_company(company):
            moves = Move.create([{
                        'product': product.id,
                        'uom': uom.id,
                        'quantity': 1,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal(1),
                        'currency': company.currency.id,
                        }])

            Move.check_origin(moves, set())
            Move.check_origin(moves, {'supplier'})
            self.assertRaises(UserWarning, Move.check_origin, moves,
                {'customer'})

    def test_assign_try(self):
        'Test Move assign_try'
        for quantity, quantities, success, result in [
                (10, [2], True, {'assigned': [2]}),
                (5, [10], False, {'assigned': [5], 'draft': [5]}),
                (0, [3], False, {'draft': [3]}),
                (6.8, [2.1, 1.7, 1.2, 1.8], True,
                    {'assigned': sorted([2.1, 1.7, 1.2, 1.8])}),
                ]:
            self._test_assign_try(quantity, quantities, success, result)

    @with_transaction()
    def _test_assign_try(self, quantity, quantities, success, result):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        uom, = Uom.search([('name', '=', 'Meter')])
        template = Template(
            name='Test Move.assign_try',
            type='goods',
            list_price=Decimal(1),
            cost_price=Decimal(0),
            cost_price_method='fixed',
            default_uom=uom,
            )
        template.save()
        product = Product(template=template.id)
        product.save()

        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])
        customer, = Location.search([('code', '=', 'CUS')])

        company = create_company()
        with set_company(company):
            move, = Move.create([{
                        'product': product.id,
                        'uom': uom.id,
                        'quantity': quantity,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal(1),
                        'currency': company.currency.id,
                        }])
            Move.do([move])

            moves = Move.create([{
                        'product': product.id,
                        'uom': uom.id,
                        'quantity': qty,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal(1),
                        'currency': company.currency.id,
                        } for qty in quantities])

            msg = 'quantity: %s, quantities: %s' % (quantity, quantities)
            self.assertEqual(Move.assign_try(moves), success, msg=msg)
            moves = Move.search([
                    ('product', '=', product.id),
                    ('from_location', '=', storage.id),
                    ('to_location', '=', customer.id),
                    ('company', '=', company.id),
                    ])
            states = defaultdict(list)
            for move in moves:
                states[move.state].append(move.quantity)
            for state in states:
                states[state].sort()
            self.assertEqual(states, result, msg=msg)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(StockTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_stock_shipment_out.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_average_cost_price.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_stock_inventory.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_stock_shipment_internal.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_stock_reporting.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
