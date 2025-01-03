# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model.exceptions import (
    RequiredValidationError, SelectionValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)


class FieldMultiSelectionTestCase(TestCase):
    "Test Field MultiSelection"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

    @property
    def Selection(self):
        return Pool().get('test.multi_selection')

    @property
    def SelectionRequired(self):
        return Pool().get('test.multi_selection_required')

    @with_transaction()
    def test_create(self):
        "Test create multi-selection"
        selection, selection_none = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }, {
                    'selects': None,
                    }])

        self.assertEqual(selection.selects, ('bar', 'foo'))
        self.assertEqual(selection_none.selects, ())

    @with_transaction()
    def test_create_not_in(self):
        "Test create multi-selection not in selection"
        with self.assertRaises(SelectionValidationError):
            self.Selection.create([{
                        'selects': ('invalid'),
                        }])

    @with_transaction()
    def test_create_dynamic(self):
        "Test create dynamic selection"
        selection_foo, selection_bar = self.Selection.create([{
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
        selection, = self.Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': None,
                    }])

        self.assertEqual(selection.dyn_selects, ())

    @with_transaction()
    def test_create_dynamic_not_in(self):
        "Test create dynamic selection not in"
        with self.assertRaises(SelectionValidationError):
            self.Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': ['foo', 'bar'],
                    }])

    @with_transaction()
    def test_create_static(self):
        "Test create static selection"
        selection, = self.Selection.create([{
                    'static_selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.static_selects, ('bar', 'foo'))

    @with_transaction()
    def test_create_static_none(self):
        "Test create static selection None"
        selection, = self.Selection.create([{
                    'static_selects': None,
                    }])

        self.assertEqual(selection.static_selects, ())

    @with_transaction()
    def test_create_static_not_in(self):
        "Test create static selection not in"
        with self.assertRaises(SelectionValidationError):
            self.Selection.create([{
                    'static_selects': ['foo', 'bar', 'invalid'],
                    }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create selection required with value"
        selection, = self.SelectionRequired.create([{
                    'selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.selects, ('bar', 'foo'))

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create selection required without value"
        with self.assertRaises(RequiredValidationError):
            self.SelectionRequired.create([{}])

    @with_transaction()
    def test_create_required_none(self):
        "Test create selection required without value"
        with self.assertRaises(RequiredValidationError):
            self.SelectionRequired.create([{
                        'selects': None,
                        }])

    @with_transaction()
    def test_create_required_empty(self):
        "Test create selection required with empty value"
        with self.assertRaises(RequiredValidationError):
            self.SelectionRequired.create([{
                        'selects': [],
                        }])

    @with_transaction()
    def test_write(self):
        "Test write selection"
        selection, = self.Selection.create([{
                    'selects': ['foo'],
                    }])

        self.Selection.write([selection], {
                'selects': ['foo', 'bar'],
                })

        self.assertEqual(selection.selects, ('bar', 'foo'))

    @with_transaction()
    def test_string(self):
        "Test string selection"
        selection, = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        self.assertEqual(selection.selects_string, ["Bar", "Foo"])

    @with_transaction()
    def test_string_none(self):
        "Test string selection none"
        selection, = self.Selection.create([{
                    'selects': None,
                    }])

        self.assertEqual(selection.selects_string, [])

    @with_transaction()
    def test_search_equals(self):
        "Test search selection equals"
        selection, = self.Selection.create([{
                    'selects': ['bar', 'foo'],
                    }])

        foo_bar = self.Selection.search([
                ('selects', '=', ['foo', 'bar']),
                ])
        foo = self.Selection.search([
                ('selects', '=', ['foo']),
                ])

        self.assertEqual(foo_bar, [selection])
        self.assertEqual(foo, [])

    @with_transaction()
    def test_search_equals_string(self):
        "Test search selection equals string"
        selection, = self.Selection.create([{
                    'selects': ['foo'],
                    }])

        foo = self.Selection.search([
                ('selects', '=', 'foo'),
                ])

        self.assertEqual(foo, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search selection equals"
        selection, = self.Selection.create([{
                    'selects': None,
                    }])

        selections = self.Selection.search([
                ('selects', '=', None),
                ])

        self.assertEqual(selections, [selection])

    @with_transaction()
    def test_search_in_string(self):
        "Test search selection in string"
        selection, = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = self.Selection.search([
                ('selects', 'in', 'foo'),
                ])
        baz = self.Selection.search([
                ('selects', 'in', 'baz'),
                ])

        self.assertEqual(foo, [selection])
        self.assertEqual(baz, [])

    @with_transaction()
    def test_search_not_in_string(self):
        "Test search selection not in string"
        selection, = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = self.Selection.search([
                ('selects', 'not in', 'foo'),
                ])
        baz = self.Selection.search([
                ('selects', 'not in', 'baz'),
                ])

        self.assertEqual(foo, [])
        self.assertEqual(baz, [selection])

    @with_transaction()
    def test_search_in_list(self):
        "Test search selection in list"
        selection, = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = self.Selection.search([
                ('selects', 'in', ['foo']),
                ])
        baz = self.Selection.search([
                ('selects', 'in', ['baz']),
                ])
        foo_baz = self.Selection.search([
                ('selects', 'in', ['foo', 'baz']),
                ])
        empty = self.Selection.search([
                ('selects', 'in', []),
                ])

        self.assertEqual(foo, [selection])
        self.assertEqual(baz, [])
        self.assertEqual(foo_baz, [selection])
        self.assertEqual(empty, [])

    @with_transaction()
    def test_search_not_in_list(self):
        "Test search selection not in list"
        selection, = self.Selection.create([{
                    'selects': ['foo', 'bar'],
                    }])

        foo = self.Selection.search([
                ('selects', 'not in', ['foo']),
                ])
        baz = self.Selection.search([
                ('selects', 'not in', ['baz']),
                ])
        foo_baz = self.Selection.search([
                ('selects', 'not in', ['foo', 'baz']),
                ])
        empty = self.Selection.search([
                ('selects', 'not in', []),
                ])

        self.assertEqual(foo, [])
        self.assertEqual(baz, [selection])
        self.assertEqual(foo_baz, [])
        self.assertEqual(empty, [selection])

    @with_transaction()
    def test_read_string(self):
        "Test reading value and string"
        foo, foo_bar, null = self.Selection.create([{
                    'selects': ['foo'],
                    }, {
                    'selects': ['foo', 'bar'],
                    }, {
                    'selects': [],
                    }])

        foo_read, foo_bar_read, null_read = self.Selection.read(
            [foo.id, foo_bar.id, null.id], ['selects:string'])

        self.assertEqual(foo_read['selects:string'], ["Foo"])
        self.assertEqual(foo_bar_read['selects:string'], ["Bar", "Foo"])
        self.assertEqual(null_read['selects:string'], [])

    @with_transaction()
    def test_read_string_dynamic_selection(self):
        "Test reading value and string of a dynamic selection"
        foo, bar, null = self.Selection.create([{
                    'selects': ['foo'],
                    'dyn_selects': ['foo', 'foobar'],
                    }, {
                    'dyn_selects': ['bar', 'baz'],
                    }, {
                    'dyn_selects': [],
                    }])

        foo_read, bar_read, null_read = self.Selection.read(
            [foo.id, bar.id, null.id], ['dyn_selects:string'])

        self.assertEqual(foo_read['dyn_selects:string'], ["Foo", "FooBar"])
        self.assertEqual(bar_read['dyn_selects:string'], ["Bar", "Baz"])
        self.assertEqual(null_read['dyn_selects:string'], [])


class FieldMultiSelectionTextTestCase(FieldMultiSelectionTestCase):
    "Test Field MultiSelection with TEXT as SQL type"

    @property
    def Selection(self):
        return Pool().get('test.multi_selection_text')

    @property
    def SelectionRequired(self):
        return Pool().get('test.multi_selection_required_text')
