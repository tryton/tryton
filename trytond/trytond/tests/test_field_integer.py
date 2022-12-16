# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from sql import Literal

from trytond.model.exceptions import (
    RequiredValidationError, DomainValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldIntegerTestCase(unittest.TestCase):
    "Test Field Integer"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create integer"
        Integer = Pool().get('test.integer')

        integer_1, integer_none = Integer.create([{
                    'integer': 1,
                    }, {
                    'integer': None,
                    }])

        self.assertEqual(integer_1.integer, 1)
        self.assertEqual(integer_none.integer, None)

    @with_transaction()
    def test_create_without_default(self):
        "Test create integer without default"
        Integer = Pool().get('test.integer')

        integer, = Integer.create([{}])

        self.assertEqual(integer.integer, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create integer with default"
        Integer = Pool().get('test.integer_default')

        integer, = Integer.create([{}])

        self.assertEqual(integer.integer, 5)

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create integer with SQL value"
        Integer = Pool().get('test.integer_default')

        integer, = Integer.create([{'integer': Literal(5)}])

        self.assertEqual(integer.integer, 5)

    @with_transaction()
    def test_create_non_integer(self):
        "Test create integer with non integer"
        Integer = Pool().get('test.integer')

        with self.assertRaises(ValueError):
            Integer.create([{
                        'integer': 'non integer',
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create integer required with value"
        Integer = Pool().get('test.integer_required')

        integer, = Integer.create([{
                    'integer': 0,
                    }])

        self.assertEqual(integer.integer, 0)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create integer required without value"
        Integer = Pool().get('test.integer_required')

        with self.assertRaises(RequiredValidationError):
            Integer.create([{}])

    @with_transaction()
    def test_create_with_domain_valid(self):
        "Test create integer with domain valid"
        Integer = Pool().get('test.integer_domain')

        integer, = Integer.create([{
                    'integer': 100,
                    }])

        self.assertEqual(integer.integer, 100)

    @with_transaction()
    def test_create_with_domain_invalid(self):
        "Test create integer with domain invalid"
        Integer = Pool().get('test.integer_domain')

        with self.assertRaises(DomainValidationError):
            Integer.create([{
                        'integer': 10,
                        }])

    @with_transaction()
    def test_search_equals(self):
        "Test search integer equals"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_1 = Integer.search([
                ('integer', '=', 1),
                ])
        integers_0 = Integer.search([
                ('integer', '=', 0),
                ])

        self.assertListEqual(integers_1, [integer])
        self.assertListEqual(integers_0, [])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search integer non equals"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_1 = Integer.search([
                ('integer', '!=', 1),
                ])
        integers_0 = Integer.search([
                ('integer', '!=', 0),
                ])

        self.assertListEqual(integers_1, [])
        self.assertListEqual(integers_0, [integer])

    @with_transaction()
    def test_search_in(self):
        "Test search integer in"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_1 = Integer.search([
                ('integer', 'in', [1]),
                ])
        integers_0 = Integer.search([
                ('integer', 'in', [0]),
                ])
        integers_empty = Integer.search([
                ('integer', 'in', []),
                ])

        self.assertListEqual(integers_1, [integer])
        self.assertListEqual(integers_0, [])
        self.assertListEqual(integers_empty, [])

    @with_transaction()
    def test_search_not_in(self):
        "Test search integer not in"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_1 = Integer.search([
                ('integer', 'not in', [1]),
                ])
        integers_0 = Integer.search([
                ('integer', 'not in', [0]),
                ])
        integers_empty = Integer.search([
                ('integer', 'not in', []),
                ])

        self.assertListEqual(integers_1, [])
        self.assertListEqual(integers_0, [integer])
        self.assertListEqual(integers_empty, [integer])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search integer in multiple"
        Integer = Pool().get('test.integer')
        integers = Integer.create([{
                    'integer': 1,
                    }, {
                    'integer': 0,
                    }])

        integers_in = Integer.search([
                ('integer', 'in', [0, 1]),
                ])

        self.assertListEqual(integers_in, integers)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search integer not in multiple"
        Integer = Pool().get('test.integer')
        Integer.create([{
                    'integer': 1,
                    }, {
                    'integer': 0,
                    }])

        integers = Integer.search([
                ('integer', 'not in', [0, 1]),
                ])

        self.assertListEqual(integers, [])

    @with_transaction()
    def test_search_less(self):
        "Test search integer less than"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_5 = Integer.search([
                ('integer', '<', 5),
                ])
        integers__5 = Integer.search([
                ('integer', '<', -5),
                ])
        integers_1 = Integer.search([
                ('integer', '<', 1),
                ])

        self.assertListEqual(integers_5, [integer])
        self.assertListEqual(integers__5, [])
        self.assertListEqual(integers_1, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search integer less than or equals"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_5 = Integer.search([
                ('integer', '<=', 5),
                ])
        integers__5 = Integer.search([
                ('integer', '<=', -5),
                ])
        integers_1 = Integer.search([
                ('integer', '<=', 1),
                ])

        self.assertListEqual(integers_5, [integer])
        self.assertListEqual(integers__5, [])
        self.assertListEqual(integers_1, [integer])

    @with_transaction()
    def test_search_greater(self):
        "Test search integer greater than"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_5 = Integer.search([
                ('integer', '>', 5),
                ])
        integers__5 = Integer.search([
                ('integer', '>', -5),
                ])
        integers_1 = Integer.search([
                ('integer', '>', 1),
                ])

        self.assertListEqual(integers_5, [])
        self.assertListEqual(integers__5, [integer])
        self.assertListEqual(integers_1, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search integer greater than or equals"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        integers_5 = Integer.search([
                ('integer', '>=', 5),
                ])
        integers__5 = Integer.search([
                ('integer', '>=', -5),
                ])
        integers_1 = Integer.search([
                ('integer', '>=', 1),
                ])

        self.assertListEqual(integers_5, [])
        self.assertListEqual(integers__5, [integer])
        self.assertListEqual(integers_1, [integer])

    @with_transaction()
    def test_write(self):
        "Test write integer"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        Integer.write([integer], {
                'integer': 0,
                })

        self.assertEqual(integer.integer, 0)

    @with_transaction()
    def test_write_non_integer(self):
        "Test write integer with non integer"
        Integer = Pool().get('test.integer')
        integer, = Integer.create([{
                    'integer': 1,
                    }])

        with self.assertRaises(ValueError):
            Integer.write([integer], {
                    'integer': 'non integer',
                    })


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldIntegerTestCase)
