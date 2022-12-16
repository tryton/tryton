# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import InvalidOperation

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.exceptions import UserError


class ImportDataTestCase(unittest.TestCase):
    'Test import_data'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_boolean(self):
        'Test boolean'
        pool = Pool()
        Boolean = pool.get('test.import_data.boolean')

        self.assertEqual(Boolean.import_data(['boolean'],
            [['True']]), 1)

        self.assertEqual(Boolean.import_data(['boolean'],
            [['1']]), 1)

        self.assertEqual(Boolean.import_data(['boolean'],
            [['False']]), 1)

        self.assertEqual(Boolean.import_data(['boolean'],
            [['0']]), 1)

        self.assertEqual(Boolean.import_data(['boolean'],
            [['']]), 1)

        self.assertEqual(Boolean.import_data(['boolean'],
            [['True'], ['False']]), 2)

        self.assertRaises(ValueError, Boolean.import_data,
            ['boolean'], [['foo']])

    @with_transaction()
    def test_integer(self):
        'Test integer'
        pool = Pool()
        Integer = pool.get('test.import_data.integer')

        self.assertEqual(Integer.import_data(['integer'],
            [['1']]), 1)

        self.assertEqual(Integer.import_data(['integer'],
            [['-1']]), 1)

        self.assertEqual(Integer.import_data(['integer'],
            [['']]), 1)

        self.assertEqual(Integer.import_data(['integer'],
            [['1'], ['2']]), 2)

        self.assertRaises(ValueError, Integer.import_data,
            ['integer'], [['1.1']])

        self.assertRaises(ValueError, Integer.import_data,
            ['integer'], [['-1.1']])

        self.assertRaises(ValueError, Integer.import_data,
            ['integer'], [['foo']])

        self.assertEqual(Integer.import_data(['integer'],
            [['0']]), 1)

    @with_transaction()
    def test_integer_required(self):
        'Test required integer'
        pool = Pool()
        IntegerRequired = pool.get('test.import_data.integer_required')
        transaction = Transaction()

        self.assertEqual(IntegerRequired.import_data(['integer'],
            [['1']]), 1)

        self.assertEqual(IntegerRequired.import_data(['integer'],
            [['-1']]), 1)

        self.assertRaises(UserError, IntegerRequired.import_data,
            ['integer'], [['']])
        transaction.rollback()

        self.assertEqual(IntegerRequired.import_data(['integer'],
            [['1'], ['2']]), 2)

        self.assertRaises(ValueError, IntegerRequired.import_data,
            ['integer'], [['1.1']])

        self.assertRaises(ValueError, IntegerRequired.import_data,
            ['integer'], [['-1.1']])

        self.assertRaises(ValueError, IntegerRequired.import_data,
            ['integer'], [['foo']])

        self.assertEqual(IntegerRequired.import_data(['integer'],
            [['0']]), 1)

    @with_transaction()
    def test_float(self):
        'Test float'
        pool = Pool()
        Float = pool.get('test.import_data.float')

        self.assertEqual(Float.import_data(['float'],
            [['1.1']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [['-1.1']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [['1']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [['']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(ValueError, Float.import_data,
            ['float'], [['foo']])

        self.assertEqual(Float.import_data(['float'],
            [['0']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [['0.0']]), 1)

    @with_transaction()
    def test_float_required(self):
        'Test required float'
        pool = Pool()
        FloatRequired = pool.get('test.import_data.float_required')
        transaction = Transaction()

        self.assertEqual(FloatRequired.import_data(['float'],
            [['1.1']]), 1)

        self.assertEqual(FloatRequired.import_data(['float'],
            [['-1.1']]), 1)

        self.assertEqual(FloatRequired.import_data(['float'],
            [['1']]), 1)

        self.assertRaises(UserError, FloatRequired.import_data,
            ['float'], [['']])
        transaction.rollback()

        self.assertEqual(FloatRequired.import_data(['float'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(ValueError, FloatRequired.import_data,
            ['float'], [['foo']])

        self.assertEqual(FloatRequired.import_data(['float'],
            [['0']]), 1)

        self.assertEqual(FloatRequired.import_data(['float'],
            [['0.0']]), 1)

    @with_transaction()
    def test_numeric(self):
        'Test numeric'
        pool = Pool()
        Numeric = pool.get('test.import_data.numeric')

        self.assertEqual(Numeric.import_data(['numeric'],
            [['1.1']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [['-1.1']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [['1']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [['']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(InvalidOperation, Numeric.import_data,
            ['numeric'], [['foo']])

        self.assertEqual(Numeric.import_data(['numeric'],
            [['0']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [['0.0']]), 1)

    @with_transaction()
    def test_numeric_required(self):
        'Test required numeric'
        pool = Pool()
        NumericRequired = pool.get('test.import_data.numeric_required')
        transaction = Transaction()

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['1.1']]), 1)

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['-1.1']]), 1)

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['1']]), 1)

        self.assertRaises(UserError, NumericRequired.import_data,
            ['numeric'], [['']])
        transaction.rollback()

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(InvalidOperation,
            NumericRequired.import_data, ['numeric'], [['foo']])

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['0']]), 1)

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['0.0']]), 1)

    @with_transaction()
    def test_char(self):
        'Test char'
        pool = Pool()
        Char = pool.get('test.import_data.char')

        self.assertEqual(Char.import_data(['char'],
            [['test']]), 1)

        self.assertEqual(Char.import_data(['char'],
            [['']]), 1)

        self.assertEqual(Char.import_data(['char'],
            [['test'], ['foo'], ['bar']]), 3)

    @with_transaction()
    def test_text(self):
        'Test text'
        pool = Pool()
        Text = pool.get('test.import_data.text')

        self.assertEqual(Text.import_data(['text'],
            [['test']]), 1)

        self.assertEqual(Text.import_data(['text'],
            [['']]), 1)

        self.assertEqual(Text.import_data(['text'],
            [['test'], ['foo'], ['bar']]), 3)

    @with_transaction()
    def test_date(self):
        'Test date'
        pool = Pool()
        Date = pool.get('test.import_data.date')

        self.assertEqual(Date.import_data(['date'],
            [['2010-01-01']]), 1)

        self.assertEqual(Date.import_data(['date'],
            [['']]), 1)

        self.assertEqual(Date.import_data(['date'],
            [['2010-01-01'], ['2010-02-01']]), 2)

        self.assertRaises(ValueError, Date.import_data,
            ['date'], [['foo']])

    @with_transaction()
    def test_datetime(self):
        'Test datetime'
        pool = Pool()
        Datetime = pool.get('test.import_data.datetime')

        self.assertEqual(Datetime.import_data(['datetime'],
            [['2010-01-01 12:00:00']]), 1)

        self.assertEqual(Datetime.import_data(['datetime'],
            [['']]), 1)

        self.assertEqual(Datetime.import_data(['datetime'],
            [['2010-01-01 12:00:00'], ['2010-01-01 13:30:00']]), 2)

        self.assertRaises(ValueError, Datetime.import_data,
            ['datetime'], [['foo']])

    @with_transaction()
    def test_selection(self):
        'Test selection'
        pool = Pool()
        Selection = pool.get('test.import_data.selection')

        self.assertEqual(Selection.import_data(['selection'],
            [['select1']]), 1)

        self.assertEqual(Selection.import_data(['selection'],
            [['']]), 1)

        self.assertEqual(Selection.import_data(['selection'],
            [['select1'], ['select2']]), 2)

        self.assertRaises(UserError, Selection.import_data,
            ['selection'], [['foo']])

    @with_transaction()
    def test_many2one(self):
        'Test many2one'
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')
        transaction = Transaction()

        self.assertEqual(Many2one.import_data(['many2one'],
            [['Test']]), 1)

        self.assertEqual(Many2one.import_data(['many2one:id'],
            [['tests.import_data_many2one_target_test']]), 1)

        self.assertEqual(Many2one.import_data(['many2one'],
            [['']]), 1)

        self.assertEqual(Many2one.import_data(['many2one'],
            [['Test'], ['Test']]), 2)

        self.assertRaises(UserError, Many2one.import_data,
            ['many2one'], [['foo']])
        transaction.rollback()

        self.assertRaises(UserError, Many2one.import_data,
            ['many2one'], [['Duplicate']])
        transaction.rollback()

        self.assertRaises(UserError, Many2one.import_data,
            ['many2one:id'], [['foo']])
        transaction.rollback()

        self.assertRaises(Exception, Many2one.import_data,
            ['many2one:id'], [['tests.foo']])
        transaction.rollback()

    @with_transaction()
    def test_many2many(self):
        'Test many2many'
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')
        transaction = Transaction()

        self.assertEqual(Many2many.import_data(['many2many'],
            [['Test 1']]), 1)

        self.assertEqual(Many2many.import_data(['many2many:id'],
            [['tests.import_data_many2many_target_test1']]), 1)

        self.assertEqual(Many2many.import_data(['many2many'],
            [['Test 1,Test 2']]), 1)

        self.assertEqual(Many2many.import_data(['many2many:id'],
            [['tests.import_data_many2many_target_test1,'
                'tests.import_data_many2many_target_test2']]), 1)

        self.assertEqual(Many2many.import_data(['many2many'],
            [['Test\\, comma']]), 1)

        self.assertEqual(Many2many.import_data(['many2many'],
            [['Test\\, comma,Test 1']]), 1)

        self.assertEqual(Many2many.import_data(['many2many'],
            [['']]), 1)

        self.assertEqual(Many2many.import_data(['many2many'],
            [['Test 1'], ['Test 2']]), 2)

        self.assertRaises(UserError, Many2many.import_data,
            ['many2many'], [['foo']])
        transaction.rollback()

        self.assertRaises(UserError, Many2many.import_data,
            ['many2many'], [['Test 1,foo']])
        transaction.rollback()

        self.assertRaises(UserError, Many2many.import_data,
            ['many2many'], [['Duplicate']])
        transaction.rollback()

        self.assertRaises(UserError, Many2many.import_data,
            ['many2many'], [['Test 1,Duplicate']])
        transaction.rollback()

    @with_transaction()
    def test_one2many(self):
        'Test one2many'
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'], [['Test', 'Test 1']]), 1)

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'],
                [['Test', 'Test 1'], ['', 'Test 2']]), 1)

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'],
                [
                    ['Test 1', 'Test 1'],
                    ['', 'Test 2'],
                    ['Test 2', 'Test 1']]), 2)

    @with_transaction()
    def test_reference(self):
        'Test reference'
        pool = Pool()
        Reference = pool.get('test.import_data.reference')
        transaction = Transaction()

        self.assertEqual(Reference.import_data(['reference'],
            [['test.import_data.reference.selection,Test']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference.__name__,
            'test.import_data.reference.selection')
        transaction.rollback()

        self.assertEqual(Reference.import_data(['reference:id'],
            [['test.import_data.reference.selection,'
                'tests.import_data_reference_selection_test']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference.__name__,
            'test.import_data.reference.selection')
        transaction.rollback()

        self.assertEqual(Reference.import_data(['reference'],
            [['']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference, None)
        transaction.rollback()

        self.assertEqual(Reference.import_data(['reference'],
            [['test.import_data.reference.selection,Test'],
                ['test.import_data.reference.selection,Test']]), 2)
        for reference in Reference.search([]):
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')
        transaction.rollback()

        self.assertRaises(UserError, Reference.import_data,
            ['reference'], [['test.import_data.reference.selection,foo']])
        transaction.rollback()

        self.assertRaises(UserError, Reference.import_data,
            ['reference'],
            [['test.import_data.reference.selection,Duplicate']])
        transaction.rollback()

        self.assertRaises(UserError, Reference.import_data,
            ['reference:id'],
            [['test.import_data.reference.selection,foo']])
        transaction.rollback()

        self.assertRaises(Exception, Reference.import_data,
            ['reference:id'],
            [['test.import_data.reference.selection,test.foo']])
        transaction.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ImportDataTestCase)
