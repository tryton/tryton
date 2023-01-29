# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import (
    RequiredValidationError, SelectionValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldSelectionTestCase(unittest.TestCase):
    "Test Field Selection"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create selection"
        Selection = Pool().get('test.selection')

        selection, selection_none = Selection.create([{
                    'select': 'arabic',
                    }, {
                    'select': None,
                    }])

        self.assertEqual(selection.select, 'arabic')
        self.assertEqual(selection_none.select, None)

    @with_transaction()
    def test_create_not_in(self):
        "Test create selection not in selection"
        Selection = Pool().get('test.selection')

        with self.assertRaises(SelectionValidationError):
            Selection.create([{
                        'select': 'chinese',
                        }])

    @with_transaction()
    def test_create_dynamic(self):
        "Test create dynamic selection"
        Selection = Pool().get('test.selection')

        selection_arabic, selection_hexa = Selection.create([{
                    'select': 'arabic',
                    'dyn_select': '1',
                    }, {
                    'select': 'hexa',
                    'dyn_select': '0x3',
                    }])

        self.assertEqual(selection_arabic.dyn_select, '1')
        self.assertEqual(selection_hexa.dyn_select, '0x3')

    @with_transaction()
    def test_create_dynamic_none(self):
        "Test create dynamic selection None"
        Selection = Pool().get('test.selection')

        selection, = Selection.create([{
                    'select': 'hexa',
                    'dyn_select': None,
                    }])

        self.assertEqual(selection.dyn_select, None)

    @with_transaction()
    def test_create_dynamic_static(self):
        "Test create dynamic selection static"
        Selection = Pool().get('test.selection')

        selection, = Selection.create([{
                    'dyn_select_static': '1',
                    }])

        self.assertEqual(selection.dyn_select_static, '1')

    @with_transaction()
    def test_create_dynamic_not_in(self):
        "Test create selection not in"
        Selection = Pool().get('test.selection')

        with self.assertRaises(SelectionValidationError):
            Selection.create([{
                        'select': 'arabic',
                        'dyn_select': '0x3',
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create selection required with value"
        Selection = Pool().get('test.selection_required')

        selection, = Selection.create([{
                    'select': 'latin',
                    }])

        self.assertEqual(selection.select, 'latin')

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create selection required without value"
        Selection = Pool().get('test.selection_required')

        with self.assertRaises(RequiredValidationError):
            Selection.create([{}])

    @with_transaction()
    def test_create_required_none(self):
        "Test create selection required without value"
        Selection = Pool().get('test.selection_required')

        with self.assertRaises(RequiredValidationError):
            Selection.create([{
                        'select': None,
                        }])

    @with_transaction()
    def test_search_order_label(self):
        "Test search order by label"
        pool = Pool()
        Selection = pool.get('test.selection_label')

        Selection.create([{'select': v} for v in ['a', 'b', 'c']])
        records = Selection.search([], order=[('select', 'ASC')])
        values = [r.select for r in records]

        self.assertListEqual(values, ['c', 'b', 'a'])

    @with_transaction()
    def test_search_order_fixed_selection(self):
        "Test search order by fixed selection"
        pool = Pool()
        Selection = pool.get('test.selection')

        Selection.create([{'select': v} for v in ['', 'arabic', 'hexa']])
        records = Selection.search([], order=[('select', 'DESC')])
        values = [r.select for r in records]

        self.assertListEqual(values, ['hexa', 'arabic', ''])

    @with_transaction()
    def test_search_order_static_selection(self):
        "Test search order by static selection"
        pool = Pool()
        Selection = pool.get('test.selection')

        Selection.create([
                {'dyn_select_static': str(i)} for i in range(1, 4)])
        records = Selection.search([], order=[('dyn_select_static', 'DESC')])
        values = [r.dyn_select_static for r in records]

        self.assertListEqual(values, ['3', '2', '1'])

    @with_transaction()
    def test_search_order_dynamic_selection(self):
        "Test search order by dynamic selection"
        pool = Pool()
        Selection = pool.get('test.selection')

        Selection.create([
                {'select': 'arabic', 'dyn_select': str(i)}
                for i in range(1, 4)])
        Selection.create([
                {'select': 'hexa', 'dyn_select': hex(i)}
                for i in range(1, 4)])
        records = Selection.search([], order=[('dyn_select', 'DESC')])
        values = [r.dyn_select for r in records]

        self.assertListEqual(values, ['3', '2', '1', '0x3', '0x2', '0x1'])

    @with_transaction()
    def test_search_order_unsorted(self):
        "Test search order with unsorted selection"
        pool = Pool()
        Selection = pool.get('test.selection')

        Selection.create([{
                    'unsorted_select': 'second',
                    }, {
                    'unsorted_select': 'last',
                    }, {
                    'unsorted_select': 'first',
                    }])

        records = Selection.search([], order=[('unsorted_select', 'ASC')])
        values = [r.unsorted_select for r in records]

        self.assertListEqual(values, ['first', 'second', 'last'])

    @with_transaction()
    def test_string(self):
        "Test string selection"
        Selection = Pool().get('test.selection')
        selection, selection_none = Selection.create([{
                    'select': 'arabic',
                    }, {
                    'select': None,
                    }])

        self.assertEqual(selection.select_string, 'Arabic')
        self.assertEqual(selection_none.select_string, '')

    @with_transaction()
    def test_string_dynamic(self):
        "Test string dynamic selection"
        Selection = Pool().get('test.selection')

        selection_arabic, selection_hexa = Selection.create([{
                    'select': 'arabic',
                    'dyn_select': '1',
                    }, {
                    'select': 'hexa',
                    'dyn_select': '0x3',
                    }])

        self.assertEqual(selection_arabic.dyn_select_string, '1')
        self.assertEqual(selection_hexa.dyn_select_string, '0x3')

    @with_transaction()
    def test_string_dynamic_none(self):
        "Test string dynamic selection None"
        Selection = Pool().get('test.selection')

        selection, = Selection.create([{
                    'select': 'hexa',
                    'dyn_select': None,
                    }])

        self.assertEqual(selection.dyn_select_string, '')

    @with_transaction()
    def test_string_dynamic_selection_static(self):
        "Test string dynamic selection static"
        Selection = Pool().get('test.selection')

        selection, = Selection.create([{
                    'dyn_select_static': '1',
                    }])

        self.assertEqual(selection.dyn_select_static_string, '1')

    @with_transaction()
    def test_read_string(self):
        "Test reading value and string"
        Selection = Pool().get('test.selection')

        arabic, null = Selection.create([
                {
                    'select': 'arabic',
                    },
                {
                    'select': None,
                    },
                ])
        arabic_read, null_read = Selection.read(
            [arabic.id, null.id], ['select:string'])

        self.assertEqual(arabic_read['select:string'], 'Arabic')
        self.assertEqual(null_read['select:string'], '')

    @with_transaction()
    def test_read_string_dynamic_selection(self):
        "Test reading value and string of dynamic selection"
        Selection = Pool().get('test.selection')

        one, null = Selection.create([
                {
                    'select': 'arabic',
                    'dyn_select': '1'
                    },
                {
                    'select': None,
                    },
                ])
        one_read, null_read = Selection.read(
            [one.id, null.id], ['dyn_select:string'])

        self.assertEqual(one_read['dyn_select:string'], '1')
        self.assertEqual(null_read['dyn_select:string'], '')
