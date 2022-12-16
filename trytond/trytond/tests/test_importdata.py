#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module


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
        cursor = DB.cursor()

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['True']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['False']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['0']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['True'], ['False']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.boolean.import_data(cursor, USER, ['boolean'],
            [['foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0020integer(self):
        '''
        Test integer.
        '''
        cursor = DB.cursor()

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['-1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['1'], ['2']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['1.1']], CONTEXT)[0] == -1)

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['-1.1']], CONTEXT)[0] == -1)

        self.assert_(self.integer.import_data(cursor, USER, ['integer'],
            [['foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0030float(self):
        '''
        Test float.
        '''
        cursor = DB.cursor()

        self.assert_(self.float.import_data(cursor, USER, ['float'], [['1.1']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.float.import_data(cursor, USER, ['float'],
            [['-1.1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.float.import_data(cursor, USER, ['float'], [['1']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.float.import_data(cursor, USER, ['float'], [['']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.float.import_data(cursor, USER, ['float'], [['1.1'],
            ['2.2']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.float.import_data(cursor, USER, ['float'], [['foo']],
            CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0040numeric(self):
        '''
        Test numeric.
        '''
        cursor = DB.cursor()

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['1.1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['-1.1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['1.1'], ['2.2']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.numeric.import_data(cursor, USER, ['numeric'],
            [['foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0050char(self):
        '''
        Test char.
        '''
        cursor = DB.cursor()

        self.assert_(self.char.import_data(cursor, USER, ['char'], [['test']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.char.import_data(cursor, USER, ['char'], [['']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.char.import_data(cursor, USER, ['char'], [['test'],
            ['foo'], ['bar']], CONTEXT) == (3, 0, 0, 0))

        cursor.rollback()
        cursor.close()

    def test0060text(self):
        '''
        Test text.
        '''
        cursor = DB.cursor()

        self.assert_(self.text.import_data(cursor, USER, ['text'], [['test']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.text.import_data(cursor, USER, ['text'], [['']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.text.import_data(cursor, USER, ['text'], [['test'],
            ['foo'], ['bar']], CONTEXT) == (3, 0, 0, 0))

        cursor.rollback()
        cursor.close()

    def test0070sha(self):
        '''
        Test sha.
        '''
        cursor = DB.cursor()

        self.assert_(self.sha.import_data(cursor, USER, ['sha'], [['test']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.sha.import_data(cursor, USER, ['sha'], [['']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.sha.import_data(cursor, USER, ['sha'], [['test'],
            ['foo']], CONTEXT) == (2, 0, 0, 0))

        cursor.rollback()
        cursor.close()

    def test0080date(self):
        '''
        Test date.
        '''
        cursor = DB.cursor()

        self.assert_(self.date.import_data(cursor, USER, ['date'],
            [['2010-01-01']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.date.import_data(cursor, USER, ['date'], [['']],
            CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.date.import_data(cursor, USER, ['date'], [
            ['2010-01-01'], ['2010-02-01']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.date.import_data(cursor, USER, ['date'], [['foo']],
            CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0090datetime(self):
        '''
        Test datetime.
        '''
        cursor = DB.cursor()

        self.assert_(self.datetime.import_data(cursor, USER, ['datetime'],
            [['2010-01-01 12:00:00']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.datetime.import_data(cursor, USER, ['datetime'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.datetime.import_data(cursor, USER, ['datetime'],
            [['2010-01-01 12:00:00'], ['2010-01-01 13:30:00']], CONTEXT) == (2,
                0, 0, 0))

        self.assert_(self.datetime.import_data(cursor, USER, ['datetime'],
            [['foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0100selection(self):
        '''
        Test selection.
        '''
        cursor = DB.cursor()

        self.assert_(self.selection.import_data(cursor, USER, ['selection'],
            [['select1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.selection.import_data(cursor, USER, ['selection'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.selection.import_data(cursor, USER, ['selection'],
            [['select1'], ['select2']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.selection.import_data(cursor, USER, ['selection'],
            [['foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0110many2one(self):
        '''
        Test many2one.
        '''
        cursor = DB.cursor()

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one'],
            [['Test']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one:id'],
            [['test.import_data_many2one_target_test']], CONTEXT) == (1, 0, 0,
                0))

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one'],
            [['Test'], ['Test']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one'],
            [['foo']], CONTEXT)[0] == -1)

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one'],
            [['Duplicate']], CONTEXT)[0] == -1)

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one:id'],
            [['foo']], CONTEXT)[0] == -1)

        self.assert_(self.many2one.import_data(cursor, USER, ['many2one:id'],
            [['test.foo']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0120many2many(self):
        '''
        Test many2many.
        '''
        cursor = DB.cursor()

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test 1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many:id'],
            [['test.import_data_many2many_target_test1']], CONTEXT) == (1, 0,
                0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test 1,Test 2']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many:id'],
            [['test.import_data_many2many_target_test1,' \
                    'test.import_data_many2many_target_test2']], CONTEXT) ==
            (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test\, comma']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test\, comma,Test 1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test 1'], ['Test 2']], CONTEXT) == (2, 0, 0, 0))

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['foo']], CONTEXT)[0] == -1)

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test 1,foo']], CONTEXT)[0] == -1)

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Duplicate']], CONTEXT)[0] == -1)

        self.assert_(self.many2many.import_data(cursor, USER, ['many2many'],
            [['Test 1,Duplicate']], CONTEXT)[0] == -1)

        cursor.rollback()
        cursor.close()

    def test0130one2many(self):
        '''
        Test one2many.
        '''
        cursor = DB.cursor()

        self.assert_(self.one2many.import_data(cursor, USER, ['name',
            'one2many/name'], [['Test', 'Test 1']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.one2many.import_data(cursor, USER, ['name',
            'one2many/name'], [['Test', 'Test 1'], ['', 'Test 2']], CONTEXT) ==
            (1, 0, 0, 0))

        self.assert_(self.one2many.import_data(cursor, USER, ['name',
            'one2many/name'], [['Test 1', 'Test 1'], ['', 'Test 2'], ['Test 2',
                'Test 1']], CONTEXT) == (2, 0, 0, 0))

        cursor.rollback()
        cursor.close()

    def test0140reference(self):
        '''
        Test reference.
        '''
        cursor = DB.cursor()

        self.assert_(self.reference.import_data(cursor, USER, ['reference'],
            [['test.import_data.reference.selection,Test']], CONTEXT) == (1, 0,
                0, 0))

        self.assert_(self.reference.import_data(cursor, USER, ['reference:id'],
            [['test.import_data.reference.selection,'\
                    'test.import_data_reference_selection_test']], CONTEXT) ==
            (1, 0, 0, 0))

        self.assert_(self.reference.import_data(cursor, USER, ['reference'],
            [['']], CONTEXT) == (1, 0, 0, 0))

        self.assert_(self.reference.import_data(cursor, USER, ['reference'],
            [['test.import_data.reference.selection,Test'],
                ['test.import_data.reference.selection,Test']], CONTEXT) == (2,
                    0, 0, 0))

        self.assert_(self.reference.import_data(cursor, USER, ['reference'],
            [['test.import_data.reference.selection,foo']], CONTEXT)[0] == -1)

        self.assert_(self.reference.import_data(cursor, USER, ['reference'],
            [['test.import_data.reference.selection,Duplicate']], CONTEXT)[0]
            == -1)

        self.assert_(self.reference.import_data(cursor, USER, ['reference:id'],
            [['test.import_data.reference.selection,foo']], CONTEXT)[0] == -1)

        self.assert_(self.reference.import_data(cursor, USER, ['reference:id'],
            [['test.import_data.reference.selection,test.foo']], CONTEXT)[0] ==
            -1)

        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ImportDataTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)

