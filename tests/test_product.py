# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool


class ProductTestCase(ModuleTestCase):
    'Test Product module'
    module = 'product'

    @with_transaction()
    def test_uom_non_zero_rate_factor(self):
        'Test uom non_zero_rate_factor constraint'
        pool = Pool()
        UomCategory = pool.get('product.uom.category')
        Uom = pool.get('product.uom')
        transaction = Transaction()
        category, = UomCategory.create([{'name': 'Test'}])

        self.assertRaises(Exception, Uom.create, [{
                'name': 'Test',
                'symbol': 'T',
                'category': category.id,
                'rate': 0,
                'factor': 0,
                }])
        transaction.rollback()

        def create():
            category, = UomCategory.create([{'name': 'Test'}])
            return Uom.create([{
                        'name': 'Test',
                        'symbol': 'T',
                        'category': category.id,
                        'rate': 1.0,
                        'factor': 1.0,
                        }])[0]

        uom = create()
        self.assertRaises(Exception, Uom.write, [uom], {
                'rate': 0.0,
                })
        transaction.rollback()

        uom = create()
        self.assertRaises(Exception, Uom.write, [uom], {
                'factor': 0.0,
                })
        transaction.rollback()

        uom = create()
        self.assertRaises(Exception, Uom.write, [uom], {
                'rate': 0.0,
                'factor': 0.0,
                })
        transaction.rollback()

    @with_transaction()
    def test_uom_check_factor_and_rate(self):
        'Test uom check_factor_and_rate constraint'
        pool = Pool()
        UomCategory = pool.get('product.uom.category')
        Uom = pool.get('product.uom')
        transaction = Transaction()
        category, = UomCategory.create([{'name': 'Test'}])

        self.assertRaises(Exception, Uom.create, [{
                'name': 'Test',
                'symbol': 'T',
                'category': category.id,
                'rate': 2,
                'factor': 2,
                }])
        transaction.rollback()

        def create():
            category, = UomCategory.create([{'name': 'Test'}])
            return Uom.create([{
                        'name': 'Test',
                        'symbol': 'T',
                        'category': category.id,
                        'rate': 1.0,
                        'factor': 1.0,
                        }])[0]

        uom = create()
        self.assertRaises(Exception, Uom.write, [uom], {
                'rate': 2.0,
                })
        transaction.rollback()

        uom = create()
        self.assertRaises(Exception, Uom.write, [uom], {
                'factor': 2.0,
                })
        transaction.rollback()

    @with_transaction()
    def test_uom_select_accurate_field(self):
        'Test uom select_accurate_field function'
        pool = Pool()
        Uom = pool.get('product.uom')
        tests = [
            ('Meter', 'factor'),
            ('Kilometer', 'factor'),
            ('centimeter', 'rate'),
            ('Foot', 'factor'),
            ]
        for name, result in tests:
            uom, = Uom.search([
                    ('name', '=', name),
                    ], limit=1)
            self.assertEqual(result, uom.accurate_field)

    @with_transaction()
    def test_uom_compute_qty(self):
        'Test uom compute_qty function'
        pool = Pool()
        Uom = pool.get('product.uom')
        tests = [
            ('Kilogram', 100, 'Gram', 100000, 100000),
            ('Gram', 1, 'Pound', 0.0022046226218487759, 0.0),
            ('Second', 5, 'Minute', 0.083333333333333343, 0.08),
            ('Second', 25, 'Hour', 0.0069444444444444441, 0.01),
            ('Millimeter', 3, 'Inch', 0.11811023622047245, 0.12),
            ('Millimeter', 0, 'Inch', 0, 0),
            ('Millimeter', None, 'Inch', None, None),
            ]
        for from_name, qty, to_name, result, rounded_result in tests:
            from_uom, = Uom.search([
                    ('name', '=', from_name),
                    ], limit=1)
            to_uom, = Uom.search([
                    ('name', '=', to_name),
                    ], limit=1)
            self.assertEqual(result, Uom.compute_qty(
                    from_uom, qty, to_uom, False))
            self.assertEqual(rounded_result, Uom.compute_qty(
                    from_uom, qty, to_uom, True))
        self.assertEqual(0.2, Uom.compute_qty(None, 0.2, None, False))
        self.assertEqual(0.2, Uom.compute_qty(None, 0.2, None, True))

        tests_exceptions = [
            ('Millimeter', 3, 'Pound', ValueError),
            ('Kilogram', 'not a number', 'Pound', TypeError),
            ]
        for from_name, qty, to_name, exception in tests_exceptions:
            from_uom, = Uom.search([
                    ('name', '=', from_name),
                    ], limit=1)
            to_uom, = Uom.search([
                    ('name', '=', to_name),
                    ], limit=1)
            self.assertRaises(exception, Uom.compute_qty,
                from_uom, qty, to_uom, False)
            self.assertRaises(exception, Uom.compute_qty,
                from_uom, qty, to_uom, True)
        self.assertRaises(ValueError, Uom.compute_qty,
            None, qty, to_uom, True)
        self.assertRaises(ValueError, Uom.compute_qty,
            from_uom, qty, None, True)

    @with_transaction()
    def test_uom_compute_price(self):
        'Test uom compute_price function'
        pool = Pool()
        Uom = pool.get('product.uom')
        tests = [
            ('Kilogram', Decimal('100'), 'Gram', Decimal('0.1')),
            ('Gram', Decimal('1'), 'Pound', Decimal('453.59237')),
            ('Second', Decimal('5'), 'Minute', Decimal('300')),
            ('Second', Decimal('25'), 'Hour', Decimal('90000')),
            ('Millimeter', Decimal('3'), 'Inch', Decimal('76.2')),
            ('Millimeter', Decimal('0'), 'Inch', Decimal('0')),
            ('Millimeter', None, 'Inch', None),
            ]
        for from_name, price, to_name, result in tests:
            from_uom, = Uom.search([
                    ('name', '=', from_name),
                    ], limit=1)
            to_uom, = Uom.search([
                    ('name', '=', to_name),
                    ], limit=1)
            self.assertEqual(result, Uom.compute_price(
                    from_uom, price, to_uom))
        self.assertEqual(Decimal('0.2'), Uom.compute_price(
                None, Decimal('0.2'), None))

        tests_exceptions = [
            ('Millimeter', Decimal('3'), 'Pound', ValueError),
            ('Kilogram', 'not a number', 'Pound', TypeError),
            ]
        for from_name, price, to_name, exception in tests_exceptions:
            from_uom, = Uom.search([
                    ('name', '=', from_name),
                    ], limit=1)
            to_uom, = Uom.search([
                    ('name', '=', to_name),
                    ], limit=1)
            self.assertRaises(exception, Uom.compute_price,
                from_uom, price, to_uom)
        self.assertRaises(ValueError, Uom.compute_price,
            None, price, to_uom)
        self.assertRaises(ValueError, Uom.compute_price,
            from_uom, price, None)

    @with_transaction()
    def test_product_search_domain(self):
        'Test product.product search_domain function'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')

        kilogram, = Uom.search([
                ('name', '=', 'Kilogram'),
                ], limit=1)
        millimeter, = Uom.search([
                ('name', '=', 'Millimeter'),
                ])
        pt1, pt2 = Template.create([{
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
        p, = Product.search([
                ('default_uom.name', '=', 'Kilogram'),
                ])
        self.assertEqual(p, pt1.products[0])
        p, = Product.search([
                ('default_uom.name', '=', 'Millimeter'),
                ])
        self.assertEqual(p, pt2.products[0])

    @with_transaction()
    def test_search_domain_conversion(self):
        'Test the search domain conversion'
        pool = Pool()
        Category = pool.get('product.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        category1, = Category.create([{'name': 'Category1'}])
        category2, = Category.create([{'name': 'Category2'}])
        uom, = Uom.search([], limit=1)
        values1 = {
            'name': 'Some product-1',
            'categories': [('add', [category1.id])],
            'type': 'goods',
            'list_price': Decimal('10'),
            'cost_price': Decimal('5'),
            'default_uom': uom.id,
            'products': [('create', [{}])],
            }
        values2 = {
            'name': 'Some product-2',
            'categories': [('add', [category2.id])],
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
        # domain ('template.categories', '=', 1) will return 2 records which
        # it supposed to be.
        template1, template2, template3, template4 = Template.create(
            [values1, values1.copy(), values2, values2.copy()]
            )
        self.assertEqual(Product.search([], count=True), 4)
        self.assertEqual(
            Product.search([
                    ('categories', '=', category1.id),
                    ], count=True), 2)

        self.assertEqual(
            Product.search([
                    ('template.categories', '=', category1.id),
                    ], count=True), 2)

        self.assertEqual(
            Product.search([
                    ('categories', '=', category2.id),
                    ], count=True), 2)
        self.assertEqual(
            Product.search([
                    ('template.categories', '=', category2.id),
                    ], count=True), 2)

    @with_transaction()
    def test_uom_round(self):
        'Test uom round function'
        pool = Pool()
        Uom = pool.get('product.uom')
        tests = [
            (2.53, .1, 2.5),
            (3.8, .1, 3.8),
            (3.7, .1, 3.7),
            (1.3, .5, 1.5),
            (1.1, .3, 1.2),
            (17, 10, 20),
            (7, 10, 10),
            (4, 10, 0),
            (17, 15, 15),
            (2.5, 1.4, 2.8),
            ]
        for number, precision, result in tests:
            self.assertEqual(Uom(rounding=precision).round(number), result)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ProductTestCase))
    return suite
