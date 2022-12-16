# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.exceptions import UserError
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

        with self.assertRaises(UserError):
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

        with self.assertRaises(UserError):
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

        with self.assertRaises(UserError):
            Selection.create([{}])

    @with_transaction()
    def test_create_required_none(self):
        "Test create selection required without value"
        Selection = Pool().get('test.selection_required')

        with self.assertRaises(UserError):
            Selection.create([{
                        'select': None,
                        }])

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


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldSelectionTestCase)
