# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import InvalidOperation

from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class ImportDataTestCase(unittest.TestCase):
    'Test import_data'

    def setUp(self):
        install_module('tests')
        self.boolean = POOL.get('test.import_data.boolean')
        self.integer = POOL.get('test.import_data.integer')
        self.integer_required = POOL.get('test.import_data.integer_required')
        self.float = POOL.get('test.import_data.float')
        self.float_required = POOL.get('test.import_data.float_required')
        self.numeric = POOL.get('test.import_data.numeric')
        self.numeric_required = POOL.get('test.import_data.numeric_required')
        self.char = POOL.get('test.import_data.char')
        self.text = POOL.get('test.import_data.text')
        self.date = POOL.get('test.import_data.date')
        self.datetime = POOL.get('test.import_data.datetime')
        self.selection = POOL.get('test.import_data.selection')
        self.many2one = POOL.get('test.import_data.many2one')
        self.many2many = POOL.get('test.import_data.many2many')
        self.one2many = POOL.get('test.import_data.one2many')
        self.reference = POOL.get('test.import_data.reference')

    def test0010boolean(self):
        'Test boolean'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.boolean.import_data(['boolean'],
                [['True']]), 1)

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['1']]), 1)

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['False']]), 1)

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['0']]), 1)

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['']]), 1)

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['True'], ['False']]), 2)

            self.assertRaises(ValueError, self.boolean.import_data,
                ['boolean'], [['foo']])

    def test0020integer(self):
        'Test integer'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.integer.import_data(['integer'],
                [['1']]), 1)

            self.assertEqual(self.integer.import_data(['integer'],
                [['-1']]), 1)

            self.assertEqual(self.integer.import_data(['integer'],
                [['']]), 1)

            self.assertEqual(self.integer.import_data(['integer'],
                [['1'], ['2']]), 2)

            self.assertRaises(ValueError, self.integer.import_data,
                ['integer'], [['1.1']])

            self.assertRaises(ValueError, self.integer.import_data,
                ['integer'], [['-1.1']])

            self.assertRaises(ValueError, self.integer.import_data,
                ['integer'], [['foo']])

            self.assertEqual(self.integer.import_data(['integer'],
                [['0']]), 1)

    def test0021integer_required(self):
        'Test required integer'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.integer_required.import_data(['integer'],
                [['1']]), 1)

            self.assertEqual(self.integer_required.import_data(['integer'],
                [['-1']]), 1)

            self.assertRaises(UserError, self.integer_required.import_data,
                ['integer'], [['']])
            transaction.cursor.rollback()

            self.assertEqual(self.integer_required.import_data(['integer'],
                [['1'], ['2']]), 2)

            self.assertRaises(ValueError, self.integer_required.import_data,
                ['integer'], [['1.1']])

            self.assertRaises(ValueError, self.integer_required.import_data,
                ['integer'], [['-1.1']])

            self.assertRaises(ValueError, self.integer_required.import_data,
                ['integer'], [['foo']])

            self.assertEqual(self.integer_required.import_data(['integer'],
                [['0']]), 1)

    def test0030float(self):
        'Test float'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.float.import_data(['float'],
                [['1.1']]), 1)

            self.assertEqual(self.float.import_data(['float'],
                [['-1.1']]), 1)

            self.assertEqual(self.float.import_data(['float'],
                [['1']]), 1)

            self.assertEqual(self.float.import_data(['float'],
                [['']]), 1)

            self.assertEqual(self.float.import_data(['float'],
                [['1.1'], ['2.2']]), 2)

            self.assertRaises(ValueError, self.float.import_data,
                ['float'], [['foo']])

            self.assertEqual(self.float.import_data(['float'],
                [['0']]), 1)

            self.assertEqual(self.float.import_data(['float'],
                [['0.0']]), 1)

    def test0031float_required(self):
        'Test required float'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.float_required.import_data(['float'],
                [['1.1']]), 1)

            self.assertEqual(self.float_required.import_data(['float'],
                [['-1.1']]), 1)

            self.assertEqual(self.float_required.import_data(['float'],
                [['1']]), 1)

            self.assertRaises(UserError, self.float_required.import_data,
                ['float'], [['']])
            transaction.cursor.rollback()

            self.assertEqual(self.float_required.import_data(['float'],
                [['1.1'], ['2.2']]), 2)

            self.assertRaises(ValueError, self.float_required.import_data,
                ['float'], [['foo']])

            self.assertEqual(self.float_required.import_data(['float'],
                [['0']]), 1)

            self.assertEqual(self.float_required.import_data(['float'],
                [['0.0']]), 1)

    def test0040numeric(self):
        'Test numeric'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1.1']]), 1)

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['-1.1']]), 1)

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1']]), 1)

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['']]), 1)

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1.1'], ['2.2']]), 2)

            self.assertRaises(InvalidOperation, self.numeric.import_data,
                ['numeric'], [['foo']])

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['0']]), 1)

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['0.0']]), 1)

    def test0041numeric_required(self):
        'Test required numeric'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['1.1']]), 1)

            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['-1.1']]), 1)

            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['1']]), 1)

            self.assertRaises(UserError, self.numeric_required.import_data,
                ['numeric'], [['']])
            transaction.cursor.rollback()

            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['1.1'], ['2.2']]), 2)

            self.assertRaises(InvalidOperation,
                self.numeric_required.import_data, ['numeric'], [['foo']])

            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['0']]), 1)

            self.assertEqual(self.numeric_required.import_data(['numeric'],
                [['0.0']]), 1)

    def test0050char(self):
        'Test char'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.char.import_data(['char'],
                [['test']]), 1)

            self.assertEqual(self.char.import_data(['char'],
                [['']]), 1)

            self.assertEqual(self.char.import_data(['char'],
                [['test'], ['foo'], ['bar']]), 3)

    def test0060text(self):
        'Test text'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.text.import_data(['text'],
                [['test']]), 1)

            self.assertEqual(self.text.import_data(['text'],
                [['']]), 1)

            self.assertEqual(self.text.import_data(['text'],
                [['test'], ['foo'], ['bar']]), 3)

    def test0080date(self):
        'Test date'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.date.import_data(['date'],
                [['2010-01-01']]), 1)

            self.assertEqual(self.date.import_data(['date'],
                [['']]), 1)

            self.assertEqual(self.date.import_data(['date'],
                [['2010-01-01'], ['2010-02-01']]), 2)

            self.assertRaises(ValueError, self.date.import_data,
                ['date'], [['foo']])

    def test0090datetime(self):
        'Test datetime'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.datetime.import_data(['datetime'],
                [['2010-01-01 12:00:00']]), 1)

            self.assertEqual(self.datetime.import_data(['datetime'],
                [['']]), 1)

            self.assertEqual(self.datetime.import_data(['datetime'],
                [['2010-01-01 12:00:00'], ['2010-01-01 13:30:00']]), 2)

            self.assertRaises(ValueError, self.datetime.import_data,
                ['datetime'], [['foo']])

    def test0100selection(self):
        'Test selection'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.selection.import_data(['selection'],
                [['select1']]), 1)

            self.assertEqual(self.selection.import_data(['selection'],
                [['']]), 1)

            self.assertEqual(self.selection.import_data(['selection'],
                [['select1'], ['select2']]), 2)

            self.assertRaises(UserError, self.selection.import_data,
                ['selection'], [['foo']])
            transaction.cursor.rollback()

    def test0110many2one(self):
        'Test many2one'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.many2one.import_data(['many2one'],
                [['Test']]), 1)

            self.assertEqual(self.many2one.import_data(['many2one:id'],
                [['tests.import_data_many2one_target_test']]), 1)

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['']]), 1)

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['Test'], ['Test']]), 2)

            self.assertRaises(UserError, self.many2one.import_data,
                ['many2one'], [['foo']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.many2one.import_data,
                ['many2one'], [['Duplicate']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.many2one.import_data,
                ['many2one:id'], [['foo']])
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.many2one.import_data,
                ['many2one:id'], [['tests.foo']])
            transaction.cursor.rollback()

    def test0120many2many(self):
        'Test many2many'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many:id'],
                [['tests.import_data_many2many_target_test1']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1,Test 2']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many:id'],
                [['tests.import_data_many2many_target_test1,'
                    'tests.import_data_many2many_target_test2']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test\, comma']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test\, comma,Test 1']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['']]), 1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1'], ['Test 2']]), 2)

            self.assertRaises(UserError, self.many2many.import_data,
                ['many2many'], [['foo']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.many2many.import_data,
                ['many2many'], [['Test 1,foo']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.many2many.import_data,
                ['many2many'], [['Duplicate']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.many2many.import_data,
                ['many2many'], [['Test 1,Duplicate']])
            transaction.cursor.rollback()

    def test0130one2many(self):
        'Test one2many'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'], [['Test', 'Test 1']]), 1)

            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'],
                    [['Test', 'Test 1'], ['', 'Test 2']]), 1)

            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'],
                    [
                        ['Test 1', 'Test 1'],
                        ['', 'Test 2'],
                        ['Test 2', 'Test 1']]), 2)

    def test0140reference(self):
        'Test reference'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,Test']]), 1)
            reference, = self.reference.search([])
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference:id'],
                [['test.import_data.reference.selection,'
                    'tests.import_data_reference_selection_test']]), 1)
            reference, = self.reference.search([])
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference'],
                [['']]), 1)
            reference, = self.reference.search([])
            self.assertEqual(reference.reference, None)
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,Test'],
                    ['test.import_data.reference.selection,Test']]), 2)
            for reference in self.reference.search([]):
                self.assertEqual(reference.reference.__name__,
                    'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.reference.import_data,
                ['reference'], [['test.import_data.reference.selection,foo']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.reference.import_data,
                ['reference'],
                [['test.import_data.reference.selection,Duplicate']])
            transaction.cursor.rollback()

            self.assertRaises(UserError, self.reference.import_data,
                ['reference:id'],
                [['test.import_data.reference.selection,foo']])
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.reference.import_data,
                ['reference:id'],
                [['test.import_data.reference.selection,test.foo']])
            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ImportDataTestCase)
