# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond import backend
from trytond.model.exceptions import (
    SelectionValidationError, RequiredValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class FieldMultiSelectionTestCase(unittest.TestCase):
    "Test Field MultiSelection"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create multi-selection"
        Selection = Pool().get('test.multi_selection')

        selection, selection_none = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }, {
                    'selects': None,
                    }])

        self.assertEqual(selection.selects, ('bar', 'foo'))
        self.assertEqual(selection_none.selects, None)

    @with_transaction()
    def test_create_not_in(self):
        "Test create multi-selection not in selection"
        Selection = Pool().get('test.multi_selection')

        with self.assertRaises(SelectionValidationError):
            Selection.create([{
                        'selects': ('invalid'),
                        }])

    @with_transaction()
    def test_create_dynamic(self):
        "Test create dynamic selection"
        Selection = Pool().get('test.multi_selection')

        selection_foo, selection_bar = Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': ['foo'],
                    }, {
                    'selects': ['bar'],
                    'dyn_selects': ['baz'],
                    }])

        self.assertEqual(selection_foo.dyn_selects, ('foo',))
        self.assertEqual(selection_bar.dyn_selects, ('baz',))

    @with_transaction()
    def test_create_dynamic_none(self):
        "Test create dynamic selection None"
        Selection = Pool().get('test.multi_selection')

        selection, = Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': None,
                    }])

        self.assertEqual(selection.dyn_selects, None)

    @with_transaction()
    def test_create_dynamic_not_in(self):
        "Test create dynamic selection not in"
        Selection = Pool().get('test.multi_selection')

        with self.assertRaises(SelectionValidationError):
            Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': ['foo', 'bar'],
                    }])

    @with_transaction()
    def test_create_static(self):
        "Test create static selection"
        Selection = Pool().get('test.multi_selection')

        selection, = Selection.create([{
                    'static_selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.static_selects, ('bar', 'foo'))

    @with_transaction()
    def test_create_static_none(self):
        "Test create static selection None"
        Selection = Pool().get('test.multi_selection')

        selection, = Selection.create([{
                    'static_selects': None,
                    }])

        self.assertEqual(selection.static_selects, None)

    @with_transaction()
    def test_create_static_not_in(self):
        "Test create static selection not in"
        Selection = Pool().get('test.multi_selection')

        with self.assertRaises(SelectionValidationError):
            Selection.create([{
                    'static_selects': ['foo', 'bar', 'invalid'],
                    }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create selection required with value"
        Selection = Pool().get('test.multi_selection_required')

        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.selects, ('bar', 'foo'))

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create selection required without value"
        Selection = Pool().get('test.multi_selection_required')

        with self.assertRaises(RequiredValidationError):
            Selection.create([{}])

    @with_transaction()
    def test_create_required_none(self):
        "Test create selection required without value"
        Selection = Pool().get('test.multi_selection_required')

        with self.assertRaises(RequiredValidationError):
            Selection.create([{
                        'selects': None,
                        }])

    @with_transaction()
    def test_create_required_empty(self):
        "Test create selection required with empty value"
        Selection = Pool().get('test.multi_selection_required')

        with self.assertRaises(RequiredValidationError):
            Selection.create([{
                        'selects': [],
                        }])

    @with_transaction()
    def test_write(self):
        "Test write selection"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo'],
                    }])

        Selection.write([selection], {
                'selects': ['foo', 'bar'],
                })

        self.assertEqual(selection.selects, ('bar', 'foo'))

    @with_transaction()
    def test_string(self):
        "Test string selection"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.selects_string, ["Bar", "Foo"])

    @with_transaction()
    def test_string_none(self):
        "Test string selection none"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': None,
                    }])

        self.assertEqual(selection.selects_string, None)

    @with_transaction()
    def test_search_equals(self):
        "Test search selection equals"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['bar', 'foo'],
                    }])

        foo_bar = Selection.search([
                ('selects', '=', ['foo', 'bar']),
                ])
        foo = Selection.search([
                ('selects', '=', ['foo']),
                ])

        self.assertEqual(foo_bar, [selection])
        self.assertEqual(foo, [])

    @with_transaction()
    def test_search_equals_string(self):
        "Test search selection equals string"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo'],
                    }])

        foo = Selection.search([
                ('selects', '=', 'foo'),
                ])

        self.assertEqual(foo, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search selection equals"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': None,
                    }])

        selections = Selection.search([
                ('selects', '=', None),
                ])

        self.assertEqual(selections, [selection])

    @with_transaction()
    def test_search_in_string(self):
        "Test search selection in string"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = Selection.search([
                ('selects', 'in', 'foo'),
                ])
        baz = Selection.search([
                ('selects', 'in', 'baz'),
                ])

        self.assertEqual(foo, [selection])
        self.assertEqual(baz, [])

    @with_transaction()
    def test_search_not_in_string(self):
        "Test search selection not in string"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = Selection.search([
                ('selects', 'not in', 'foo'),
                ])
        baz = Selection.search([
                ('selects', 'not in', 'baz'),
                ])

        self.assertEqual(foo, [])
        self.assertEqual(baz, [selection])

    @with_transaction()
    def test_search_in_list(self):
        "Test search selection in list"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = Selection.search([
                ('selects', 'in', ['foo']),
                ])
        baz = Selection.search([
                ('selects', 'in', ['baz']),
                ])
        foo_baz = Selection.search([
                ('selects', 'in', ['foo', 'baz']),
                ])
        empty = Selection.search([
                ('selects', 'in', []),
                ])

        self.assertEqual(foo, [selection])
        self.assertEqual(baz, [])
        self.assertEqual(foo_baz, [selection])
        self.assertEqual(empty, [])

    @with_transaction()
    def test_search_not_in_list(self):
        "Test search selection not in list"
        Selection = Pool().get('test.multi_selection')
        selection, = Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = Selection.search([
                ('selects', 'not in', ['foo']),
                ])
        baz = Selection.search([
                ('selects', 'not in', ['baz']),
                ])
        foo_baz = Selection.search([
                ('selects', 'not in', ['foo', 'baz']),
                ])
        empty = Selection.search([
                ('selects', 'not in', []),
                ])

        self.assertEqual(foo, [])
        self.assertEqual(baz, [selection])
        self.assertEqual(foo_baz, [])
        self.assertEqual(empty, [selection])


@unittest.skipIf(
    backend.name != 'postgresql', 'jsonb only supported by postgresql')
class FieldMultiSelectionJSONBTestCase(FieldMultiSelectionTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_model()

    @classmethod
    @with_transaction()
    def setup_model(cls):
        connection = Transaction().connection
        if backend.Database().get_version(connection) < (9, 2):
            return
        pool = Pool()
        for model in ['test.multi_selection', 'test.multi_selection_required']:
            Model = pool.get(model)
            cursor = connection.cursor()
            for name, field in Model._fields.items():
                if field._type == 'multiselection':
                    cursor.execute('ALTER TABLE "%s" '
                        'ALTER COLUMN %s TYPE json USING %s::json' % (
                            Model._table, name, name))
        Transaction().commit()


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in [FieldMultiSelectionTestCase,
            FieldMultiSelectionJSONBTestCase]:
        suite.addTests(func(testcase))
    return suite
