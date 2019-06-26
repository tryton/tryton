# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal, InvalidOperation

from sql import Literal

from trytond.model.exceptions import (
    RequiredValidationError, DigitsValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldNumericTestCase(unittest.TestCase):
    "Test Field Numeric"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create numeric"
        Numeric = Pool().get('test.numeric')

        numeric_1_1, numeric_none = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }, {
                    'numeric': None,
                    }])

        self.assertEqual(numeric_1_1.numeric, Decimal('1.1'))
        self.assertEqual(numeric_none.numeric, None)

    @with_transaction()
    def test_create_20_digits(self):
        "Test create number 20 digits"
        Numeric = Pool().get('test.numeric')

        numeric, = Numeric.create([{
                    'numeric': Decimal('0.1234567890123456789'),
                    }])

        self.assertEqual(numeric.numeric, Decimal('0.1234567890123456789'))

    @with_transaction()
    def test_create_without_default(self):
        "Test create numeric without default"
        Numeric = Pool().get('test.numeric')

        numeric, = Numeric.create([{}])

        self.assertEqual(numeric.numeric, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create numeric with default"
        Numeric = Pool().get('test.numeric_default')

        numeric, = Numeric.create([{}])

        self.assertEqual(numeric.numeric, Decimal('5.5'))

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create numeric with SQL value"
        Numeric = Pool().get('test.numeric')

        numeric, = Numeric.create([{'numeric': Literal(5.) / Literal(2.)}])

        self.assertEqual(numeric.numeric, Decimal('2.5'))

    @with_transaction()
    def test_create_non_numeric(self):
        "Test create numeric with non numeric"
        Numeric = Pool().get('test.numeric')

        with self.assertRaises(InvalidOperation):
            Numeric.create([{
                        'numeric': 'non numeric',
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create numeric required with value"
        Numeric = Pool().get('test.numeric_required')

        numeric, = Numeric.create([{
                    'numeric': Decimal('0'),
                    }])

        self.assertEqual(numeric.numeric, Decimal('0'))

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create numeric required without value"
        Numeric = Pool().get('test.numeric_required')

        with self.assertRaises(RequiredValidationError):
            Numeric.create([{}])

    @with_transaction()
    def test_create_digits_valid(self):
        "Test create numeric with digits"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 1,
                    'numeric': Decimal('1.1'),
                    }])

        self.assertEqual(numeric.numeric, Decimal('1.1'))

    @with_transaction()
    def test_create_digits_invalid(self):
        "Test create numeric with invalid digits"
        Numeric = Pool().get('test.numeric_digits')

        with self.assertRaises(DigitsValidationError):
            Numeric.create([{
                    'digits': 1,
                    'numeric': Decimal('1.11'),
                    }])

    @with_transaction()
    def test_create_digits_none(self):
        "Test create numeric with not digits"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': None,
                    'numeric': Decimal('0.123456789012345'),
                    }])

        self.assertEqual(numeric.numeric, Decimal('0.123456789012345'))

    @with_transaction()
    def test_create_10_digits(self):
        "Test create a numeric with 10 digits"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 10,
                    'numeric': Decimal('0.04'),
                    }])

        self.assertEqual(numeric.numeric, Decimal('0.04'))

    @with_transaction()
    def test_create_10_digits_invalid(self):
        "Test create a numeric with 11 digits on with 10 limit"
        Numeric = Pool().get('test.numeric_digits')

        with self.assertRaises(DigitsValidationError):
            Numeric.create([{
                        'digits': 10,
                        'numeric': Decimal('1.11111111111'),
                        }])

    @with_transaction()
    def test_search_equals(self):
        "Test search numeric equals"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_1_1 = Numeric.search([
                ('numeric', '=', Decimal('1.1')),
                ])
        numerics_0 = Numeric.search([
                ('numeric', '=', Decimal('0')),
                ])

        self.assertListEqual(numerics_1_1, [numeric])
        self.assertListEqual(numerics_0, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search numeric equals None"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': None,
                    }])

        numerics = Numeric.search([
                ('numeric', '=', None),
                ])

        self.assertListEqual(numerics, [numeric])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search numeric non equals"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_1_1 = Numeric.search([
                ('numeric', '!=', Decimal('1.1')),
                ])
        numerics_0 = Numeric.search([
                ('numeric', '!=', Decimal('0')),
                ])

        self.assertListEqual(numerics_1_1, [])
        self.assertListEqual(numerics_0, [numeric])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search numeric non equals None"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': None,
                    }])

        numerics = Numeric.search([
                ('numeric', '!=', None),
                ])

        self.assertListEqual(numerics, [])

    @with_transaction()
    def test_search_in(self):
        "Test search numeric in"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_1_1 = Numeric.search([
                ('numeric', 'in', [Decimal('1.1')]),
                ])
        numerics_0 = Numeric.search([
                ('numeric', 'in', [Decimal('0')]),
                ])
        numerics_empty = Numeric.search([
                ('numeric', 'in', []),
                ])

        self.assertListEqual(numerics_1_1, [numeric])
        self.assertListEqual(numerics_0, [])
        self.assertListEqual(numerics_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search numeric in [None]"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': None,
                    }])

        numerics = Numeric.search([
                ('numeric', 'in', [None]),
                ])

        self.assertListEqual(numerics, [numeric])

    @with_transaction()
    def test_search_not_in(self):
        "Test search numeric not in"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_1_1 = Numeric.search([
                ('numeric', 'not in', [Decimal('1.1')]),
                ])
        numerics_0 = Numeric.search([
                ('numeric', 'not in', [Decimal('0')]),
                ])
        numerics_empty = Numeric.search([
                ('numeric', 'not in', []),
                ])

        self.assertListEqual(numerics_1_1, [])
        self.assertListEqual(numerics_0, [numeric])
        self.assertListEqual(numerics_empty, [numeric])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search numeric in [None]"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': None,
                    }])

        numerics = Numeric.search([
                ('numeric', 'not in', [None]),
                ])

        self.assertListEqual(numerics, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search numeric in multiple"
        Numeric = Pool().get('test.numeric')
        numerics = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }, {
                    'numeric': Decimal('0'),
                    }])

        numerics_in = Numeric.search([
                ('numeric', 'in', [Decimal('0'), Decimal('1.1')]),
                ])

        self.assertListEqual(numerics_in, numerics)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search numeric not in multiple"
        Numeric = Pool().get('test.numeric')
        Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }, {
                    'numeric': Decimal('0'),
                    }])

        numerics = Numeric.search([
                ('numeric', 'not in', [Decimal('0'), Decimal('1.1')]),
                ])

        self.assertListEqual(numerics, [])

    @with_transaction()
    def test_search_less(self):
        "Test search numeric less than"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_5 = Numeric.search([
                ('numeric', '<', Decimal('5')),
                ])
        numerics__5 = Numeric.search([
                ('numeric', '<', Decimal('-5')),
                ])
        numerics_1_1 = Numeric.search([
                ('numeric', '<', Decimal('1.1')),
                ])

        self.assertListEqual(numerics_5, [numeric])
        self.assertListEqual(numerics__5, [])
        self.assertListEqual(numerics_1_1, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search numeric less than or equals"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_5 = Numeric.search([
                ('numeric', '<=', Decimal('5')),
                ])
        numerics__5 = Numeric.search([
                ('numeric', '<=', Decimal('-5')),
                ])
        numerics_1_1 = Numeric.search([
                ('numeric', '<=', Decimal('1.1')),
                ])

        self.assertListEqual(numerics_5, [numeric])
        self.assertListEqual(numerics__5, [])
        self.assertListEqual(numerics_1_1, [numeric])

    @with_transaction()
    def test_search_greater(self):
        "Test search numeric greater than"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_5 = Numeric.search([
                ('numeric', '>', Decimal('5')),
                ])
        numerics__5 = Numeric.search([
                ('numeric', '>', Decimal('-5')),
                ])
        numerics_1_1 = Numeric.search([
                ('numeric', '>', Decimal('1.1')),
                ])

        self.assertListEqual(numerics_5, [])
        self.assertListEqual(numerics__5, [numeric])
        self.assertListEqual(numerics_1_1, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search numeric greater than or equals"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        numerics_5 = Numeric.search([
                ('numeric', '>=', Decimal('5')),
                ])
        numerics__5 = Numeric.search([
                ('numeric', '>=', Decimal('-5')),
                ])
        numerics_1_1 = Numeric.search([
                ('numeric', '>=', Decimal('1.1')),
                ])

        self.assertListEqual(numerics_5, [])
        self.assertListEqual(numerics__5, [numeric])
        self.assertListEqual(numerics_1_1, [numeric])

    @with_transaction()
    def test_numeric_search_cast(self):
        "Test search numeric cast"
        pool = Pool()
        Numeric = pool.get('test.numeric')
        numeric1, numeric2 = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }, {
                    'numeric': Decimal('100.0'),
                    }])

        numerics = Numeric.search([
                ('numeric', '<', Decimal('5')),
                ])

        self.assertEqual(numerics, [numeric1])

    @with_transaction()
    def test_write(self):
        "Test write numeric"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        Numeric.write([numeric], {
                'numeric': Decimal('0'),
                })

        self.assertEqual(numeric.numeric, Decimal('0'))

    @with_transaction()
    def test_write_non_numeric(self):
        "Test write numeric with non numeric"
        Numeric = Pool().get('test.numeric')
        numeric, = Numeric.create([{
                    'numeric': Decimal('1.1'),
                    }])

        with self.assertRaises(InvalidOperation):
            Numeric.write([numeric], {
                    'numeric': 'non numeric',
                    })

    @with_transaction()
    def test_write_digits_invalid_value(self):
        "Test write numeric with invalid value for digits"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 1,
                    'numeric': Decimal('1.1'),
                    }])

        with self.assertRaises(DigitsValidationError):
            Numeric.write([numeric], {
                    'numeric': Decimal('1.11'),
                    })

    @with_transaction()
    def test_write_digits_invalid_value_small(self):
        "Test write numeric with invalid small value for digits"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 1,
                    'numeric': Decimal('1.1'),
                    }])

        with self.assertRaises(DigitsValidationError):
            Numeric.write([numeric], {
                    'numeric': Decimal('1.10000000000000001'),
                    })

    @with_transaction()
    def test_write_digits_invalid_digits(self):
        "Test write number with invalid digits for value"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 2,
                    'numeric': Decimal('1.11'),
                    }])

        with self.assertRaises(DigitsValidationError):
            Numeric.write([numeric], {
                    'digits': 1,
                    })

    @with_transaction()
    def test_write_digits_invalid_digits_0(self):
        "Test write number with invalid digits for value"
        Numeric = Pool().get('test.numeric_digits')

        numeric, = Numeric.create([{
                    'digits': 1,
                    'numeric': Decimal('1.1'),
                    }])

        with self.assertRaises(DigitsValidationError):
            Numeric.write([numeric], {
                    'digits': 0,
                    })


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldNumericTestCase)
