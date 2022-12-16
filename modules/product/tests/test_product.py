# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class ProductTestCase(ModuleTestCase):
    'Test Product module'
    module = 'product'

    def setUp(self):
        super(ProductTestCase, self).setUp()
        self.uom = POOL.get('product.uom')
        self.uom_category = POOL.get('product.uom.category')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.category = POOL.get('product.category')

    def test0010uom_non_zero_rate_factor(self):
        'Test uom non_zero_rate_factor constraint'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category, = self.uom_category.create([{'name': 'Test'}])
            transaction.cursor.commit()

            self.assertRaises(Exception, self.uom.create, [{
                    'name': 'Test',
                    'symbol': 'T',
                    'category': category.id,
                    'rate': 0,
                    'factor': 0,
                    }])
            transaction.cursor.rollback()

            uom, = self.uom.create([{
                        'name': 'Test',
                        'symbol': 'T',
                        'category': category.id,
                        'rate': 1.0,
                        'factor': 1.0,
                        }])
            transaction.cursor.commit()

            self.assertRaises(Exception, self.uom.write, [uom], {
                    'rate': 0.0,
                    })
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.uom.write, [uom], {
                    'factor': 0.0,
                    })
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.uom.write, [uom], {
                    'rate': 0.0,
                    'factor': 0.0,
                    })
            transaction.cursor.rollback()

    def test0020uom_check_factor_and_rate(self):
        'Test uom check_factor_and_rate constraint'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            category, = self.uom_category.search([
                    ('name', '=', 'Test'),
                    ], limit=1)

            self.assertRaises(Exception, self.uom.create, [{
                    'name': 'Test',
                    'symbol': 'T',
                    'category': category.id,
                    'rate': 2,
                    'factor': 2,
                    }])
            transaction.cursor.rollback()

            uom, = self.uom.search([
                    ('name', '=', 'Test'),
                    ], limit=1)

            self.assertRaises(Exception, self.uom.write, [uom],
                {
                    'rate': 2.0,
                    })
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.uom.write, [uom],
                {
                    'factor': 2.0,
                    })
            transaction.cursor.rollback()

    def test0030uom_select_accurate_field(self):
        'Test uom select_accurate_field function'
        tests = [
            ('Meter', 'factor'),
            ('Kilometer', 'factor'),
            ('centimeter', 'rate'),
            ('Foot', 'factor'),
            ]
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for name, result in tests:
                uom, = self.uom.search([
                        ('name', '=', name),
                        ], limit=1)
                self.assertEqual(result, uom.accurate_field)

    def test0040uom_compute_qty(self):
        'Test uom compute_qty function'
        tests = [
            ('Kilogram', 100, 'Gram', 100000, 100000),
            ('Gram', 1, 'Pound', 0.0022046226218487759, 0.0),
            ('Second', 5, 'Minute', 0.083333333333333343, 0.08),
            ('Second', 25, 'Hour', 0.0069444444444444441, 0.01),
            ('Millimeter', 3, 'Inch', 0.11811023622047245, 0.12),
            ]
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for from_name, qty, to_name, result, rounded_result in tests:
                from_uom, = self.uom.search([
                        ('name', '=', from_name),
                        ], limit=1)
                to_uom, = self.uom.search([
                        ('name', '=', to_name),
                        ], limit=1)
                self.assertEqual(result, self.uom.compute_qty(from_uom,
                        qty, to_uom, False))
                self.assertEqual(rounded_result, self.uom.compute_qty(
                        from_uom, qty, to_uom, True))

            self.assertEqual(10, self.uom.compute_qty(None, 10, to_uom))
            self.assertEqual(10, self.uom.compute_qty(None, 10, to_uom, True))
            self.assertEqual(0, self.uom.compute_qty(from_uom, 0, to_uom))
            self.assertEqual(0,
                self.uom.compute_qty(from_uom, 0, to_uom, True))
            self.assertEqual(10, self.uom.compute_qty(from_uom, 10, None))
            self.assertEqual(10,
                self.uom.compute_qty(from_uom, 10, None, True))

    def test0050uom_compute_price(self):
        'Test uom compute_price function'
        tests = [
            ('Kilogram', Decimal('100'), 'Gram', Decimal('0.1')),
            ('Gram', Decimal('1'), 'Pound', Decimal('453.59237')),
            ('Second', Decimal('5'), 'Minute', Decimal('300')),
            ('Second', Decimal('25'), 'Hour', Decimal('90000')),
            ('Millimeter', Decimal('3'), 'Inch', Decimal('76.2')),
            ]
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for from_name, price, to_name, result in tests:
                from_uom, = self.uom.search([
                        ('name', '=', from_name),
                        ], limit=1)
                to_uom, = self.uom.search([
                        ('name', '=', to_name),
                        ], limit=1)
                self.assertEqual(result, self.uom.compute_price(from_uom,
                        price, to_uom))

    def test0060product_search_domain(self):
        'Test product.product search_domain function'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            kilogram, = self.uom.search([
                    ('name', '=', 'Kilogram'),
                    ], limit=1)
            millimeter, = self.uom.search([
                    ('name', '=', 'Millimeter'),
                    ])
            pt1, pt2 = self.template.create([{
                        'name': 'P1',
                        'type': 'goods',
                        'list_price': Decimal(20),
                        'cost_price': Decimal(10),
                        'default_uom': kilogram.id,
                        'products': [('create', [{
                                        'code': '1',
                                        }])]
                        }, {
                        'name': 'P2',
                        'type': 'goods',
                        'list_price': Decimal(20),
                        'cost_price': Decimal(10),
                        'default_uom': millimeter.id,
                        'products': [('create', [{
                                        'code': '2',
                                        }])]
                        }])
            p, = self.product.search([
                    ('default_uom.name', '=', 'Kilogram'),
                    ])
            self.assertEqual(p, pt1.products[0])
            p, = self.product.search([
                    ('default_uom.name', '=', 'Millimeter'),
                    ])
            self.assertEqual(p, pt2.products[0])

    def test0060search_domain_conversion(self):
        'Test the search domain conversion'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            category1, = self.category.create([{'name': 'Category1'}])
            category2, = self.category.create([{'name': 'Category2'}])
            uom, = self.uom.search([], limit=1)
            values1 = {
                'name': 'Some product-1',
                'category': category1.id,
                'type': 'goods',
                'list_price': Decimal('10'),
                'cost_price': Decimal('5'),
                'default_uom': uom.id,
                'products': [('create', [{}])],
                }
            values2 = {
                'name': 'Some product-2',
                'category': category2.id,
                'type': 'goods',
                'list_price': Decimal('10'),
                'cost_price': Decimal('5'),
                'default_uom': uom.id,
                'products': [('create', [{}])],
                }

            # This is a false positive as there is 1 product with the
            # template 1 and the same product with category 1. If you do not
            # create two categories (or any other relation on the template
            # model) you wont be able to check as in most cases the
            # id of the template and the related model would be same (1).
            # So two products have been created with same category. So that
            # domain ('template.category', '=', 1) will return 2 records which
            # it supposed to be.
            template1, template2, template3, template4 = self.template.create(
                [values1, values1.copy(), values2, values2.copy()]
                )
            self.assertEqual(self.product.search([], count=True), 4)
            self.assertEqual(
                self.product.search([
                    ('category', '=', category1.id),
                    ], count=True), 2)

            self.assertEqual(
                self.product.search([
                    ('template.category', '=', category1.id),
                    ], count=True), 2)

            self.assertEqual(
                self.product.search([
                    ('category', '=', category2.id),
                    ], count=True), 2)
            self.assertEqual(
                self.product.search([
                    ('template.category', '=', category2.id),
                    ], count=True), 2)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ProductTestCase))
    return suite
