# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import unittest
from decimal import Decimal

from trytond.model.exceptions import ImportDataError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


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

        for value in ['True', '1', 'False', '0', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Boolean.import_data(['boolean'], [[value]]), 1)

    @with_transaction()
    def test_boolean_many_rows(self):
        "Test boolean many rows"
        pool = Pool()
        Boolean = pool.get('test.import_data.boolean')

        self.assertEqual(
            Boolean.import_data(['boolean'], [['True'], ['False']]), 2)

    @with_transaction()
    def test_boolean_invalid(self):
        "Test boolean invalid value"
        pool = Pool()
        Boolean = pool.get('test.import_data.boolean')

        with self.assertRaises(ImportDataError):
            Boolean.import_data(['boolean'], [['foo']])

    @with_transaction()
    def test_integer(self):
        'Test integer'
        pool = Pool()
        Integer = pool.get('test.import_data.integer')

        for value in ['1', '0', 0, 1, '-1', '', None]:
            with self.subTest(value=value):
                self.assertEqual(
                    Integer.import_data(['integer'], [[value]]), 1)

    @with_transaction()
    def test_integer_many_rows(self):
        "Test integer many rows"
        pool = Pool()
        Integer = pool.get('test.import_data.integer')

        self.assertEqual(
            Integer.import_data(['integer'], [['1'], ['2']]), 2)

    @with_transaction()
    def test_integer_invalid(self):
        "Test integer invalid value"
        pool = Pool()
        Integer = pool.get('test.import_data.integer')

        for value in ['1.1', '-1.1', 'foo']:
            with self.subTest(value=value):
                with self.assertRaises(ImportDataError):
                    Integer.import_data(['integer'], [[value]])

    @with_transaction()
    def test_float(self):
        'Test float'
        pool = Pool()
        Float = pool.get('test.import_data.float')

        for value in [
                '1.1', 0.0, 1.1, '-1.1', '1', '', '1.1', '0', '0.0', None]:
            with self.subTest(value=value):
                self.assertEqual(
                    Float.import_data(['float'], [[value]]), 1)

    @with_transaction()
    def test_float_invalid(self):
        "Test float invalid value"
        pool = Pool()
        Float = pool.get('test.import_data.float')

        with self.assertRaises(ImportDataError):
            Float.import_data(['float'], [['foo']])

    @with_transaction()
    def test_numeric(self):
        'Test numeric'
        pool = Pool()
        Numeric = pool.get('test.import_data.numeric')

        for value in [
                '1.1', Decimal('1.1'), '-1.1', '1',
                Decimal('0.0'), '0', '0.0', '', None]:
            with self.subTest(value=value):
                self.assertEqual(
                    Numeric.import_data(['numeric'], [[value]]), 1)

    @with_transaction()
    def test_numeric_invalid(self):
        pool = Pool()
        Numeric = pool.get('test.import_data.numeric')

        with self.assertRaises(ImportDataError):
            Numeric.import_data(['numeric'], [['foo']])

    @with_transaction()
    def test_char(self):
        'Test char'
        pool = Pool()
        Char = pool.get('test.import_data.char')

        for value in ['test', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Char.import_data(['char'], [[value]]), 1)

    @with_transaction()
    def test_char_many_rows(self):
        "Test char many rows"
        pool = Pool()
        Char = pool.get('test.import_data.char')

        self.assertEqual(
            Char.import_data(['char'], [['test'], ['foo'], ['bar']]), 3)

    @with_transaction()
    def test_text(self):
        'Test text'
        pool = Pool()
        Text = pool.get('test.import_data.text')

        for value in ['test', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Text.import_data(['text'], [[value]]), 1)

    @with_transaction()
    def test_text_many_rows(self):
        "Test text many rows"
        pool = Pool()
        Text = pool.get('test.import_data.text')

        self.assertEqual(
            Text.import_data(['text'], [['test'], ['foo'], ['bar']]), 3)

    @with_transaction()
    def test_date(self):
        'Test date'
        pool = Pool()
        Date = pool.get('test.import_data.date')

        for value in ['2010-01-01', dt.date(2019, 3, 13), '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Date.import_data(['date'], [[value]]), 1)

    @with_transaction()
    def test_date_many_rows(self):
        "Test date many rows"
        pool = Pool()
        Date = pool.get('test.import_data.date')

        self.assertEqual(
            Date.import_data(['date'], [['2010-01-01'], ['2010-02-01']]), 2)

    @with_transaction()
    def test_date_invalid(self):
        "Test date invalid value"
        pool = Pool()
        Date = pool.get('test.import_data.date')

        with self.assertRaises(ImportDataError):
            Date.import_data(['date'], [['foo']])

    @with_transaction()
    def test_datetime(self):
        'Test datetime'
        pool = Pool()
        Datetime = pool.get('test.import_data.datetime')

        for value in [
                '2010-01-01 12:00:00', dt.datetime(2019, 3, 13, 12, 0), '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Datetime.import_data(['datetime'], [[value]]), 1)

    @with_transaction()
    def test_datetime_many_rows(self):
        "Test datetime many rows"
        pool = Pool()
        Datetime = pool.get('test.import_data.datetime')

        self.assertEqual(
            Datetime.import_data(
                ['datetime'], [
                    ['2010-01-01 12:00:00'], ['2010-01-01 13:30:00']]), 2)

    @with_transaction()
    def test_datetime_invalid(self):
        "Test datetime invalid value"
        pool = Pool()
        Datetime = pool.get('test.import_data.datetime')

        with self.assertRaises(ImportDataError):
            Datetime.import_data(['datetime'], [['foo']])

    @with_transaction()
    def test_timedelta(self):
        'Test timedelta'
        pool = Pool()
        Timedelta = pool.get('test.import_data.timedelta')

        for value in [
                '00:00', '0:00:00', '01:00:00', '36:00:00', '0:00:00.0001',
                dt.timedelta(
                    weeks=2, days=3, hours=8, minutes=50, seconds=30.45),
                30.45]:
            with self.subTest(value=value):
                self.assertEqual(
                    Timedelta.import_data(['timedelta'], [[value]]), 1)

    @with_transaction()
    def test_timedelta_invalid(self):
        'Test timedelta'
        pool = Pool()
        Timedelta = pool.get('test.import_data.timedelta')

        with self.assertRaises(ImportDataError):
            Timedelta.import_data(['timedelta'], [['foo']])

    @with_transaction()
    def test_selection(self):
        'Test selection'
        pool = Pool()
        Selection = pool.get('test.import_data.selection')

        for value in ['select1', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Selection.import_data(['selection'], [[value]]), 1)

    @with_transaction()
    def test_selection_many_rows(self):
        'Test selection many rows'
        pool = Pool()
        Selection = pool.get('test.import_data.selection')

        self.assertEqual(
            Selection.import_data(['selection'], [['select1'], ['select2']]),
            2)

    @with_transaction()
    def test_many2one(self):
        'Test many2one'
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')

        for value in ['Test', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Many2one.import_data(['many2one'], [[value]]), 1)

    @with_transaction()
    def test_many2one_id(self):
        "Test many2one with id"
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')

        self.assertEqual(
            Many2one.import_data(
                ['many2one:id'], [['tests.import_data_many2one_target_test']]),
            1)

    @with_transaction()
    def test_many2one_many_rows(self):
        "Test many2one many rows"
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')

        self.assertEqual(
            Many2one.import_data(['many2one'], [['Test'], ['Test']]), 2)

    @with_transaction()
    def test_many2one_invalid(self):
        "Test many2one invalid value"
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')

        for value in ['foo', 'Duplicate']:
            with self.subTest(value=value):
                with self.assertRaises(ImportDataError):
                    Many2one.import_data(['many2one'], [[value]])

    @with_transaction()
    def test_many2one_id_invalid(self):
        "Test many2one invalid id"
        pool = Pool()
        Many2one = pool.get('test.import_data.many2one')

        for value in ['foo', 'tests.foo']:
            with self.subTest(value=value):
                with self.assertRaises(ImportDataError):
                    Many2one.import_data(['many2one:id'], [[value]])

    @with_transaction()
    def test_many2many(self):
        'Test many2many'
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')

        for value in [
                'Test 1', 'Test\\, comma', 'Test\\, comma,Test 1',
                'Test 1,Test 2', '']:
            with self.subTest(value=value):
                self.assertEqual(
                    Many2many.import_data(['many2many'], [[value]]), 1)

    @with_transaction()
    def test_many2many_id(self):
        "Test many2many with id"
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')

        for value in [
                'tests.import_data_many2many_target_test1',
                'tests.import_data_many2many_target_test1,'
                'tests.import_data_many2many_target_test2']:
            with self.subTest(value=value):
                self.assertEqual(
                    Many2many.import_data(['many2many:id'], [[value]]), 1)

    @with_transaction()
    def test_many2many_many_rows(self):
        "Test many2many many rows"
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')

        self.assertEqual(
            Many2many.import_data(['many2many'], [['Test 1'], ['Test 2']]), 2)

    @with_transaction()
    def test_many2many_invalid(self):
        "Test many2many invalid value"
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')

        for value in ['foo', 'Test 1,foo', 'Duplicate', 'Test 1,Duplicate']:
            with self.subTest(value=value):
                with self.assertRaises(ImportDataError):
                    Many2many.import_data(['many2many'], [[value]])

    @with_transaction()
    def test_one2many(self):
        'Test one2many'
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'], [['Test', 'Test 1']]), 1)

    @with_transaction()
    def test_one2many_many_targets(self):
        "Test one2many with many targets"
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'],
                [['Test', 'Test 1'], ['', 'Test 2']]), 1)

    @with_transaction()
    def test_one2many_many_rows(self):
        "Test one2many many rows"
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many/name'],
                [
                    ['Test 1', 'Test 1'],
                    ['', 'Test 2'],
                    ['Test 2', 'Test 1']]), 2)

    @with_transaction()
    def test_many_one2many(self):
        "Test many one2many"
        pool = Pool()
        One2many = pool.get('test.import_data.one2manies')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many1/name', 'one2many2/name'],
                [["Test", "Test 1", "Test 2"],
                    ['', '', "Test 3"]]), 1)

        record, = One2many.search([])

        self.assertEqual(len(record.one2many1), 1)
        self.assertEqual(len(record.one2many2), 2)

    @with_transaction()
    def test_many_one2many_empty_last(self):
        "Test many one2many with empty last"
        pool = Pool()
        One2many = pool.get('test.import_data.one2manies')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many1/name', 'one2many2/name'],
                [["Test", "Test 1", "Test 2"],
                    ['', "Test 3", '']]), 1)

        record, = One2many.search([])

        self.assertEqual(len(record.one2many1), 2)
        self.assertEqual(len(record.one2many2), 1)

    @with_transaction()
    def test_many_one2many_multiple_empty(self):
        "Test many one2many with multiple empty"
        pool = Pool()
        One2many = pool.get('test.import_data.one2manies')

        self.assertEqual(One2many.import_data(
                ['name', 'one2many1/name', 'one2many2/name'],
                [["Test", "Test 1", "Test 2"],
                    ['', "Test 3", ''],
                    ['', '', "Test 4"]]), 1)

        record, = One2many.search([])

        self.assertEqual(len(record.one2many1), 2)
        self.assertEqual(len(record.one2many2), 2)

    @with_transaction()
    def test_reference(self):
        'Test reference'
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        self.assertEqual(Reference.import_data(['reference'],
            [['test.import_data.reference.selection,Test']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference.__name__,
            'test.import_data.reference.selection')

    @with_transaction()
    def test_reference_id(self):
        "Test reference with id"
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        self.assertEqual(Reference.import_data(['reference:id'],
            [['test.import_data.reference.selection,'
                'tests.import_data_reference_selection_test']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference.__name__,
            'test.import_data.reference.selection')

    @with_transaction()
    def test_reference_empty(self):
        "Test reference empty"
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        self.assertEqual(Reference.import_data(['reference'],
            [['']]), 1)
        reference, = Reference.search([])
        self.assertEqual(reference.reference, None)

    @with_transaction()
    def test_reference_many_rows(self):
        "Test reference many rows"
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        self.assertEqual(Reference.import_data(['reference'],
            [['test.import_data.reference.selection,Test'],
                ['test.import_data.reference.selection,Test']]), 2)
        for reference in Reference.search([]):
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')

    @with_transaction()
    def test_reference_invalid(self):
        "Test reference invalid value"
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        for value in [
                'test.import_data.reference.selection,foo',
                'test.import_data.reference.selection,Duplicate',
                'test.import_data.reference.selection,test.foo']:
            with self.subTest(value=value):
                with self.assertRaises(ImportDataError):
                    Reference.import_data(['reference'], [[value]])

    @with_transaction()
    def test_reference_id_invalid(self):
        "Test reference invalid id"
        pool = Pool()
        Reference = pool.get('test.import_data.reference')

        with self.assertRaises(ImportDataError):
            Reference.import_data(
                ['reference:id'],
                [['test.import_data.reference.selection,foo']])

    @with_transaction()
    def test_binary_bytes(self):
        "Test binary bytes"
        pool = Pool()
        Binary = pool.get('test.import_data.binary')

        self.assertEqual(Binary.import_data(['data'], [[b'data']]), 1)
        record, = Binary.search([])
        self.assertEqual(record.data, b'data')

    @with_transaction()
    def test_binary_base64(self):
        "Test binary base64"
        pool = Pool()
        Binary = pool.get('test.import_data.binary')

        self.assertEqual(Binary.import_data(['data'], [['ZGF0YQ==']]), 1)
        record, = Binary.search([])
        self.assertEqual(record.data, b'data')

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
    def test_update_many2many(self):
        "Test update many2many"
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')
        Target = pool.get('test.import_data.many2many.target')

        record = Many2many(many2many=[{'name': "Foo"}])
        record.save()
        target = Target(name="Bar")
        target.save()

        count = Many2many.import_data(
            ['id', 'many2many'],
            [[record.id, "Bar"]])

        self.assertEqual(count, 1)
        self.assertEqual([m.name for m in record.many2many], ["Bar"])

    @with_transaction()
    def test_update_many2many_id(self):
        "Test update many2many with id"
        pool = Pool()
        Many2many = pool.get('test.import_data.many2many')

        record = Many2many(many2many=[{'name': "Foo"}])
        record.save()

        count = Many2many.import_data(
            ['id', 'many2many:id'],
            [[record.id, 'tests.import_data_many2many_target_test1']])

        self.assertEqual(count, 1)
        self.assertEqual([m.name for m in record.many2many], ["Test 1"])

    @with_transaction()
    def test_update_one2many(self):
        "Test update one2many"
        pool = Pool()
        One2many = pool.get('test.import_data.one2many')
        Target = pool.get('test.import_data.one2many.target')
        record = One2many(name="test", one2many=[
                Target(name="foo"), Target(name="test")])
        record.save()
        target, _ = record.one2many

        count = One2many.import_data(
            ['id', 'one2many/id', 'one2many/name'],
            [[record.id, target.id, "bar"],
                ['', '', "baz"]])

        self.assertEqual(count, 1)
        self.assertEqual(len(record.one2many), 2)
        self.assertEqual([t.name for t in record.one2many], ["bar", "baz"])
        self.assertFalse(Target.search([('name', '=', "test")]))
