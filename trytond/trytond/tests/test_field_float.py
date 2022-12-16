# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldFloatTestCase(unittest.TestCase):
    "Test Field Float"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create float"
        Float = Pool().get('test.float')

        float_1_1, float_none = Float.create([{
                    'float': 1.1,
                    }, {
                    'float': None,
                    }])

        self.assertEqual(float_1_1.float, 1.1)
        self.assertEqual(float_none.float, None)

    @with_transaction()
    def test_create_15_digits(self):
        "Test create float 15 digits"
        Float = Pool().get('test.float')

        float_, = Float.create([{
                    'float': 0.123456789012345,
                    }])

        self.assertEqual(float_.float, 0.123456789012345)

    @with_transaction()
    def test_create_without_default(self):
        "Test create float without default"
        Float = Pool().get('test.float')

        float_, = Float.create([{}])

        self.assertEqual(float_.float, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create float with default"
        Float = Pool().get('test.float_default')

        float_, = Float.create([{}])

        self.assertEqual(float_.float, 5.5)

    @with_transaction()
    def test_create_non_float(self):
        "Test create float with non float"
        Float = Pool().get('test.float')

        with self.assertRaises(ValueError):
            Float.create([{
                        'float': 'non float',
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create float required with value"
        Float = Pool().get('test.float_required')

        float_, = Float.create([{
                    'float': 0,
                    }])

        self.assertEqual(float_.float, 0)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create float required without value"
        Float = Pool().get('test.float_required')

        with self.assertRaises(UserError):
            Float.create([{}])

    @with_transaction()
    def test_create_digits_valid(self):
        "Test create float with digits"
        Float = Pool().get('test.float_digits')

        float_, = Float.create([{
                    'digits': 1,
                    'float': 1.1,
                    }])

        self.assertEqual(float_.float, 1.1)

    @with_transaction()
    def test_create_digits_invalid(self):
        "Test create float with invalid digits"
        Float = Pool().get('test.float_digits')

        with self.assertRaises(UserError):
            Float.create([{
                        'digits': 1,
                        'float': 1.11,
                        }])

    @with_transaction()
    def test_float_digits_none(self):
        "Test create float with no digits"
        Float = Pool().get('test.float_digits')

        record, = Float.create([{
                    'float': 0.123456789012345,
                    'digits': None,
                    }])

        self.assertEqual(record.float, 0.123456789012345)

    @with_transaction()
    def test_search_equals(self):
        "Test search float equals"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_1_1 = Float.search([
                ('float', '=', 1.1),
                ])
        floats_0 = Float.search([
                ('float', '=', 0),
                ])

        self.assertListEqual(floats_1_1, [float_])
        self.assertListEqual(floats_0, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search float equals None"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': None,
                    }])

        floats = Float.search([
                ('float', '=', None),
                ])

        self.assertListEqual(floats, [float_])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search float non equals"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_1_1 = Float.search([
                ('float', '!=', 1.1),
                ])
        floats_0 = Float.search([
                ('float', '!=', 0),
                ])

        self.assertListEqual(floats_1_1, [])
        self.assertListEqual(floats_0, [float_])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search float non equals None"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': None,
                    }])

        floats = Float.search([
                ('float', '!=', None),
                ])

        self.assertListEqual(floats, [])

    @with_transaction()
    def test_search_in(self):
        "Test search float in"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_1_1 = Float.search([
                ('float', 'in', [1.1]),
                ])
        floats_0 = Float.search([
                ('float', 'in', [0]),
                ])
        floats_empty = Float.search([
                ('float', 'in', []),
                ])

        self.assertListEqual(floats_1_1, [float_])
        self.assertListEqual(floats_0, [])
        self.assertListEqual(floats_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search float in [None]"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': None,
                    }])

        floats = Float.search([
                ('float', 'in', [None]),
                ])

        self.assertListEqual(floats, [float_])

    @with_transaction()
    def test_search_not_in(self):
        "Test search float_ not in"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_1_1 = Float.search([
                ('float', 'not in', [1.1]),
                ])
        floats_0 = Float.search([
                ('float', 'not in', [0]),
                ])
        floats_empty = Float.search([
                ('float', 'not in', []),
                ])

        self.assertListEqual(floats_1_1, [])
        self.assertListEqual(floats_0, [float_])
        self.assertListEqual(floats_empty, [float_])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search float in [None]"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': None,
                    }])

        floats = Float.search([
                ('float', 'not in', [None]),
                ])

        self.assertListEqual(floats, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search float in multiple"
        Float = Pool().get('test.float')
        floats = Float.create([{
                    'float': 1.1,
                    }, {
                    'float': 0,
                    }])

        floats_in = Float.search([
                ('float', 'in', [0, 1.1]),
                ])

        self.assertListEqual(floats_in, floats)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search float_ not in multiple"
        Float = Pool().get('test.float')
        Float.create([{
                    'float': 1.1,
                    }, {
                    'float': 0,
                    }])

        floats = Float.search([
                ('float', 'not in', [0, 1.1]),
                ])

        self.assertListEqual(floats, [])

    @with_transaction()
    def test_search_less(self):
        "Test search float_ less than"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_5 = Float.search([
                ('float', '<', 5),
                ])
        floats__5 = Float.search([
                ('float', '<', -5),
                ])
        floats_1_1 = Float.search([
                ('float', '<', 1.1),
                ])

        self.assertListEqual(floats_5, [float_])
        self.assertListEqual(floats__5, [])
        self.assertListEqual(floats_1_1, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search float_ less than or equals"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_5 = Float.search([
                ('float', '<=', 5),
                ])
        floats__5 = Float.search([
                ('float', '<=', -5),
                ])
        floats_1 = Float.search([
                ('float', '<=', 1.1),
                ])

        self.assertListEqual(floats_5, [float_])
        self.assertListEqual(floats__5, [])
        self.assertListEqual(floats_1, [float_])

    @with_transaction()
    def test_search_greater(self):
        "Test search float_ greater than"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_5 = Float.search([
                ('float', '>', 5),
                ])
        floats__5 = Float.search([
                ('float', '>', -5),
                ])
        floats_1_1 = Float.search([
                ('float', '>', 1.1),
                ])

        self.assertListEqual(floats_5, [])
        self.assertListEqual(floats__5, [float_])
        self.assertListEqual(floats_1_1, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search float greater than or equals"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        floats_5 = Float.search([
                ('float', '>=', 5),
                ])
        floats__5 = Float.search([
                ('float', '>=', -5),
                ])
        floats_1 = Float.search([
                ('float', '>=', 1.1),
                ])

        self.assertListEqual(floats_5, [])
        self.assertListEqual(floats__5, [float_])
        self.assertListEqual(floats_1, [float_])

    @with_transaction()
    def test_write(self):
        "Test write float"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        Float.write([float_], {
                'float': 0,
                })

        self.assertEqual(float_.float, 0)

    @with_transaction()
    def test_write_non_float(self):
        "Test write float with non float"
        Float = Pool().get('test.float')
        float_, = Float.create([{
                    'float': 1.1,
                    }])

        with self.assertRaises(ValueError):
            Float.write([float_], {
                    'float': 'non float',
                    })

    @with_transaction()
    def test_write_digits_invalid_value(self):
        "Test write float with invalid value for digits"
        Float = Pool().get('test.float_digits')

        float_, = Float.create([{
                    'digits': 1,
                    'float': 1.1,
                    }])

        with self.assertRaises(UserError):
            Float.write([float_], {
                    'float': 1.11,
                    })

    @with_transaction()
    def test_write_digits_invalid_digits(self):
        "Test write float with invalid digits for value"
        Float = Pool().get('test.float_digits')

        float_, = Float.create([{
                    'digits': 1,
                    'float': 1.1,
                    }])

        with self.assertRaises(UserError):
            Float.write([float_], {
                    'digits': 0,
                    })


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldFloatTestCase)
