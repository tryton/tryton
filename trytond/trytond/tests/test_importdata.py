#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class ImportDataTestCase(unittest.TestCase):
    '''
    Test import_data.
    '''

    def setUp(self):
        install_module('test')
        self.boolean = POOL.get('test.import_data.boolean')
        self.integer = POOL.get('test.import_data.integer')
        self.float = POOL.get('test.import_data.float')
        self.numeric = POOL.get('test.import_data.numeric')
        self.char = POOL.get('test.import_data.char')
        self.text = POOL.get('test.import_data.text')
        self.sha = POOL.get('test.import_data.sha')
        self.date = POOL.get('test.import_data.date')
        self.datetime = POOL.get('test.import_data.datetime')
        self.selection = POOL.get('test.import_data.selection')
        self.many2one = POOL.get('test.import_data.many2one')
        self.many2many = POOL.get('test.import_data.many2many')
        self.one2many = POOL.get('test.import_data.one2many')
        self.reference = POOL.get('test.import_data.reference')

    def test0010boolean(self):
        '''
        Test boolean.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.boolean.import_data(['boolean'],
                [['True']]), (1, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['1']]), (1, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['False']]), (1, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['0']]), (1, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['True'], ['False']]), (2, 0, 0, 0))

            self.assertEqual(self.boolean.import_data(['boolean'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0020integer(self):
        '''
        Test integer.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.integer.import_data(['integer'],
                [['1']]), (1, 0, 0, 0))

            self.assertEqual(self.integer.import_data(['integer'],
                [['-1']]), (1, 0, 0, 0))

            self.assertEqual(self.integer.import_data(['integer'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.integer.import_data(['integer'],
                [['1'], ['2']]), (2, 0, 0, 0))

            self.assertEqual(self.integer.import_data(['integer'],
                [['1.1']])[0], -1)

            self.assertEqual(self.integer.import_data(['integer'],
                [['-1.1']])[0], -1)

            self.assertEqual(self.integer.import_data(['integer'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0030float(self):
        '''
        Test float.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.float.import_data(['float'],
                [['1.1']]), (1, 0, 0, 0))

            self.assertEqual(self.float.import_data(['float'],
                [['-1.1']]), (1, 0, 0, 0))

            self.assertEqual(self.float.import_data(['float'],
                [['1']]), (1, 0, 0, 0))

            self.assertEqual(self.float.import_data(['float'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.float.import_data(['float'],
                [['1.1'], ['2.2']]), (2, 0, 0, 0))

            self.assertEqual(self.float.import_data(['float'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0040numeric(self):
        '''
        Test numeric.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1.1']]), (1, 0, 0, 0))

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['-1.1']]), (1, 0, 0, 0))

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1']]), (1, 0, 0, 0))

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['1.1'], ['2.2']]), (2, 0, 0, 0))

            self.assertEqual(self.numeric.import_data(['numeric'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0050char(self):
        '''
        Test char.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.char.import_data(['char'],
                [['test']]), (1, 0, 0, 0))

            self.assertEqual(self.char.import_data(['char'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.char.import_data(['char'],
                [['test'], ['foo'], ['bar']]), (3, 0, 0, 0))

            transaction.cursor.rollback()

    def test0060text(self):
        '''
        Test text.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.text.import_data(['text'],
                [['test']]), (1, 0, 0, 0))

            self.assertEqual(self.text.import_data(['text'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.text.import_data(['text'],
                [['test'], ['foo'], ['bar']]), (3, 0, 0, 0))

            transaction.cursor.rollback()

    def test0070sha(self):
        '''
        Test sha.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.sha.import_data(['sha'],
                [['test']]), (1, 0, 0, 0))

            self.assertEqual(self.sha.import_data(['sha'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.sha.import_data(['sha'],
                [['test'], ['foo']]), (2, 0, 0, 0))

            transaction.cursor.rollback()

    def test0080date(self):
        '''
        Test date.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.date.import_data(['date'],
                [['2010-01-01']]), (1, 0, 0, 0))

            self.assertEqual(self.date.import_data(['date'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.date.import_data(['date'],
                [['2010-01-01'], ['2010-02-01']]), (2, 0, 0, 0))

            self.assertEqual(self.date.import_data(['date'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0090datetime(self):
        '''
        Test datetime.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.datetime.import_data(['datetime'],
                [['2010-01-01 12:00:00']]), (1, 0, 0, 0))

            self.assertEqual(self.datetime.import_data(['datetime'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.datetime.import_data(['datetime'],
                [['2010-01-01 12:00:00'], ['2010-01-01 13:30:00']]),
                (2, 0, 0, 0))

            self.assertEqual(self.datetime.import_data(['datetime'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0100selection(self):
        '''
        Test selection.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.selection.import_data(['selection'],
                [['select1']]), (1, 0, 0, 0))

            self.assertEqual(self.selection.import_data(['selection'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.selection.import_data(['selection'],
                [['select1'], ['select2']]), (2, 0, 0, 0))

            self.assertEqual(self.selection.import_data(['selection'],
                [['foo']])[0], -1)

            transaction.cursor.rollback()

    def test0110many2one(self):
        '''
        Test many2one.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.many2one.import_data(['many2one'],
                [['Test']]), (1, 0, 0, 0))

            self.assertEqual(self.many2one.import_data(['many2one:id'],
                [['test.import_data_many2one_target_test']]), (1, 0, 0, 0))

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['Test'], ['Test']]), (2, 0, 0, 0))

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['foo']])[0], -1)

            self.assertEqual(self.many2one.import_data(['many2one'],
                [['Duplicate']])[0], -1)

            self.assertEqual(self.many2one.import_data(['many2one:id'],
                [['foo']])[0], -1)

            self.assertEqual(self.many2one.import_data(['many2one:id'],
                [['test.foo']])[0], -1)

            transaction.cursor.rollback()

    def test0120many2many(self):
        '''
        Test many2many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many:id'],
                [['test.import_data_many2many_target_test1']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1,Test 2']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many:id'],
                [['test.import_data_many2many_target_test1,'
                    'test.import_data_many2many_target_test2']]),
                (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test\, comma']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test\, comma,Test 1']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['']]), (1, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1'], ['Test 2']]), (2, 0, 0, 0))

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['foo']])[0], -1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1,foo']])[0], -1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Duplicate']])[0], -1)

            self.assertEqual(self.many2many.import_data(['many2many'],
                [['Test 1,Duplicate']])[0], -1)

            transaction.cursor.rollback()

    def test0130one2many(self):
        '''
        Test one2many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'], [['Test', 'Test 1']]),
                (1, 0, 0, 0))

            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'], [
                        ['Test', 'Test 1'], ['', 'Test 2']]),
                (1, 0, 0, 0))

            self.assertEqual(self.one2many.import_data(
                    ['name', 'one2many/name'],
                    [
                        ['Test 1', 'Test 1'],
                        ['', 'Test 2'],
                        ['Test 2', 'Test 1']]),
                (2, 0, 0, 0))

            transaction.cursor.rollback()

    def test0140reference(self):
        '''
        Test reference.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,Test']]),
                (1, 0, 0, 0))
            reference, = self.reference.search([])
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference:id'],
                [['test.import_data.reference.selection,'
                    'test.import_data_reference_selection_test']]),
                (1, 0, 0, 0))
            reference, = self.reference.search([])
            self.assertEqual(reference.reference.__name__,
                'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference'],
                [['']]), (1, 0, 0, 0))
            reference, = self.reference.search([])
            self.assertEqual(reference.reference, None)
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,Test'],
                    ['test.import_data.reference.selection,Test']]),
                (2, 0, 0, 0))
            for reference in self.reference.search([]):
                self.assertEqual(reference.reference.__name__,
                    'test.import_data.reference.selection')
            transaction.cursor.rollback()

            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,foo']])[0], -1)

            self.assertEqual(self.reference.import_data(['reference'],
                [['test.import_data.reference.selection,Duplicate']])[0], -1)

            self.assertEqual(self.reference.import_data(['reference:id'],
                [['test.import_data.reference.selection,foo']])[0], -1)

            self.assertEqual(self.reference.import_data(['reference:id'],
                [['test.import_data.reference.selection,test.foo']])[0], -1)

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ImportDataTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
