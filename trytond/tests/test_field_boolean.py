# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldBooleanTestCase(unittest.TestCase):
    "Test Field Boolean"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create boolean"
        Boolean = Pool().get('test.boolean')

        boolean_true, boolean_false, boolean_none = Boolean.create([{
                    'boolean': True,
                    }, {
                    'boolean': False,
                    }, {
                    'boolean': None,
                    }])

        self.assertEqual(boolean_true.boolean, True)
        self.assertEqual(boolean_false.boolean, False)
        self.assertEqual(boolean_none.boolean, None)

    @with_transaction()
    def test_create_without_default(self):
        "Test create boolean without default"
        Boolean = Pool().get('test.boolean')

        boolean, = Boolean.create([{}])

        self.assertEqual(boolean.boolean, False)

    @with_transaction()
    def test_create_with_default(self):
        "Test create boolean with default"
        Boolean = Pool().get('test.boolean_default')

        boolean, = Boolean.create([{}])

        self.assertEqual(boolean.boolean, True)

    @with_transaction()
    def test_search_equals_true(self):
        "Test search boolean equals True"
        Boolean = Pool().get('test.boolean')
        boolean1, boolean2 = Boolean.create([{
                    'boolean': True,
                    }, {
                    'boolean': False,
                    }])

        booleans = Boolean.search([
                ('boolean', '=', True),
                ])

        self.assertListEqual(booleans, [boolean1])

    @with_transaction()
    def test_search_equals_false(self):
        "Test search boolean equals False"
        Boolean = Pool().get('test.boolean')
        boolean1, boolean2 = Boolean.create([{
                    'boolean': True,
                    }, {
                    'boolean': False,
                    }])

        booleans = Boolean.search([
                ('boolean', '=', False),
                ])

        self.assertListEqual(booleans, [boolean2])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search boolean non equals"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        booleans = Boolean.search([
                ('boolean', '!=', True),
                ])
        self.assertListEqual(booleans, [])

    @with_transaction()
    def test_search_in_true(self):
        "Test search boolean in [True]"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        booleans = Boolean.search([
                ('boolean', 'in', [True]),
                ])

        self.assertListEqual(booleans, [boolean])

    @with_transaction()
    def test_search_in_false(self):
        "Test search boolean in [False]"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        booleans = Boolean.search([
                ('boolean', 'in', [False]),
                ])

        self.assertListEqual(booleans, [])

    @with_transaction()
    def test_search_not_in_true(self):
        "Test search boolean not in [True]"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        booleans = Boolean.search([
                ('boolean', 'not in', [True]),
                ])

        self.assertListEqual(booleans, [])

    @with_transaction()
    def test_search_not_in_false(self):
        "Test search boolean not in [False]"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        booleans = Boolean.search([
                ('boolean', 'not in', [False]),
                ])

        self.assertListEqual(booleans, [boolean])

    @with_transaction()
    def test_search_in_true_false(self):
        "Test search boolean in [True, False]"
        Boolean = Pool().get('test.boolean')
        boolean1, boolean2 = Boolean.create([{
                    'boolean': True,
                    }, {
                    'boolean': False,
                    }])

        booleans = Boolean.search([
                ('boolean', 'in', [True, False]),
                ])

        self.assertListEqual(booleans, [boolean1, boolean2])

    @with_transaction()
    def test_search_not_in_true_false(self):
        "Test search boolean not in [True, False]"
        Boolean = Pool().get('test.boolean')
        boolean1, boolean2 = Boolean.create([{
                    'boolean': True,
                    }, {
                    'boolean': False,
                    }])

        booleans = Boolean.search([
                ('boolean', 'not in', [True, False]),
                ])

        self.assertListEqual(booleans, [])

    @with_transaction()
    def test_search_equals_false_with_none(self):
        "Test search boolean equals False with None"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': None,
                    }])

        booleans = Boolean.search([
                ('boolean', '=', False),
                ])
        self.assertListEqual(booleans, [boolean])

    @with_transaction()
    def test_search_non_equals_false_with_none(self):
        "Test search boolean non equals False with None"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': None,
                    }])

        booleans = Boolean.search([
                ('boolean', '!=', False),
                ])
        self.assertListEqual(booleans, [])

    @with_transaction()
    def test_write_false(self):
        "Test write boolean False"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': True,
                    }])

        Boolean.write([boolean], {
                'boolean': False,
                })

        self.assertEqual(boolean.boolean, False)

    @with_transaction()
    def test_write_true(self):
        "Test write boolean True"
        Boolean = Pool().get('test.boolean')
        boolean, = Boolean.create([{
                    'boolean': False,
                    }])

        Boolean.write([boolean], {
                'boolean': True,
                })

        self.assertEqual(boolean.boolean, True)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldBooleanTestCase)
