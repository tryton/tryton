# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from decimal import InvalidOperation, Decimal

from trytond.model.exceptions import (
    RequiredValidationError, SelectionValidationError, ImportDataError)
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool


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
            [[0]]), 1)

        self.assertEqual(Integer.import_data(['integer'],
            [[1]]), 1)

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

        self.assertEqual(Integer.import_data(['integer'],
            [[None]]), 1)

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

        with self.assertRaises(RequiredValidationError):
            IntegerRequired.import_data(['integer'], [['']])
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

        self.assertEqual(IntegerRequired.import_data(['integer'],
            [[0]]), 1)

        with self.assertRaises(RequiredValidationError):
            IntegerRequired.import_data(['integer'], [[None]])
        transaction.rollback()

    @with_transaction()
    def test_float(self):
        'Test float'
        pool = Pool()
        Float = pool.get('test.import_data.float')

        self.assertEqual(Float.import_data(['float'],
            [['1.1']]), 1)

        self.assertEqual(Float.import_data(['float'],
            [[0.0]]), 1)

        self.assertEqual(Float.import_data(['float'],
            [[1.1]]), 1)

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

        self.assertEqual(Float.import_data(['float'],
            [[None]]), 1)

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

        with self.assertRaises(RequiredValidationError):
            FloatRequired.import_data(['float'], [['']])
        transaction.rollback()

        self.assertEqual(FloatRequired.import_data(['float'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(ValueError, FloatRequired.import_data,
            ['float'], [['foo']])

        self.assertEqual(FloatRequired.import_data(['float'],
            [['0']]), 1)

        self.assertEqual(FloatRequired.import_data(['float'],
            [['0.0']]), 1)

        self.assertEqual(FloatRequired.import_data(['float'],
            [[0.0]]), 1)

        with self.assertRaises(RequiredValidationError):
            FloatRequired.import_data(['float'], [[None]])
        transaction.rollback()

    @with_transaction()
    def test_numeric(self):
        'Test numeric'
        pool = Pool()
        Numeric = pool.get('test.import_data.numeric')

        self.assertEqual(Numeric.import_data(['numeric'],
            [['1.1']]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [[Decimal('0.0')]]), 1)

        self.assertEqual(Numeric.import_data(['numeric'],
            [[Decimal('1.1')]]), 1)

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

        self.assertEqual(Numeric.import_data(['numeric'],
            [[None]]), 1)

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

        with self.assertRaises(RequiredValidationError):
            NumericRequired.import_data(['numeric'], [['']])
        transaction.rollback()

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['1.1'], ['2.2']]), 2)

        self.assertRaises(InvalidOperation,
            NumericRequired.import_data, ['numeric'], [['foo']])

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['0']]), 1)

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [['0.0']]), 1)

        self.assertEqual(NumericRequired.import_data(['numeric'],
            [[Decimal('0.0')]]), 1)

        with self.assertRaises(RequiredValidationError):
            NumericRequired.import_data(['numeric'], [[None]])
        transaction.rollback()

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
            [[datetime.date(2019, 3, 13)]]), 1)

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
            [[datetime.datetime(2019, 3, 13, 12, 0)]]), 1)

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

        with self.assertRaises(SelectionValidationError):
            Selection.import_data(['selection'], [['foo']])

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

        with self.assertRaises(ImportDataError):
            Many2one.import_data(['many2one'], [['foo']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Many2one.import_data(['many2one'], [['Duplicate']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Many2one.import_data(['many2one:id'], [['foo']])
        transaction.rollback()

        with self.assertRaises(KeyError):
            Many2one.import_data(['many2one:id'], [['tests.foo']])
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

        with self.assertRaises(ImportDataError):
            Many2many.import_data(['many2many'], [['foo']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Many2many.import_data(['many2many'], [['Test 1,foo']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Many2many.import_data(['many2many'], [['Duplicate']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Many2many.import_data(['many2many'], [['Test 1,Duplicate']])
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

        with self.assertRaises(ImportDataError):
            Reference.import_data(
                ['reference'], [['test.import_data.reference.selection,foo']])
        transaction.rollback()

        with self.assertRaises(ImportDataError):
            Reference.import_data(
                ['reference'],
                [['test.import_data.reference.selection,Duplicate']])
            transaction.rollback()

        with self.assertRaises(ImportDataError):
            Reference.import_data(
                ['reference:id'],
                [['test.import_data.reference.selection,foo']])
        transaction.rollback()

        with self.assertRaises(KeyError):
            Reference.import_data(
                ['reference:id'],
                [['test.import_data.reference.selection,test.foo']])
        transaction.rollback()

    @with_transaction()
    def test_update_id(self):
        "Test update with ID"
        pool = Pool()
        Char = pool.get('test.import_data.update')
        record = Char(name="foo")
        record.save()

        count = Char.import_data(['id', 'name'], [[str(record.id), "bar"]])

        record, = Char.search([])
        self.assertEqual(count, 1)
        self.assertEqual(record.name, "bar")

    @with_transaction()
    def test_update_rec_name(self):
        "Test update with rec_name"
        pool = Pool()
        Char = pool.get('test.import_data.update')
        record = Char(name="foo")
        record.save()

        count = Char.import_data(['id', 'name'], [[record.rec_name, "bar"]])

        record, = Char.search([])
        self.assertEqual(count, 1)
        self.assertEqual(record.name, "bar")

    @with_transaction()
    def test_update_one2many(self):
        "Test update one2many"
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')
        Target = pool.get('test.import_data.one2many.target')
        record = One2many(name="test", one2many=[Target(name="foo")])
        record.save()
        target, = record.one2many

        count = One2many.import_data(
            ['id', 'one2many/id', 'one2many/name'],
            [[record.id, target.id, "bar"],
                ['', '', "baz"]])

        self.assertEqual(count, 1)
        self.assertEqual(len(record.one2many), 2)
        self.assertEqual([t.name for t in record.one2many], ["bar", "baz"])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ImportDataTestCase)
