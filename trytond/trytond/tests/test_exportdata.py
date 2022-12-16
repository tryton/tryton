#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
from decimal import Decimal
import datetime
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module


class ExportDataTestCase(unittest.TestCase):
    '''
    Test export_data.
    '''

    def setUp(self):
        install_module('test')
        self.export_data = POOL.get('test.export_data')
        self.export_data_target = POOL.get('test.export_data.target')
        self.export_data_relation = POOL.get('test.export_data.relation')

    def test0010boolean(self):
        '''
        Test boolean.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'boolean': True,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['boolean'], context=CONTEXT) == [[True]])

        export2_id = self.export_data.create(cursor, USER, {
            'boolean': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['boolean'], context=CONTEXT) == [[False]])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['boolean'], context=CONTEXT) ==
            [[True], [False]])

        cursor.rollback()
        cursor.close()

    def test0020integer(self):
        '''
        Test integer.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'integer': 2,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['integer'], context=CONTEXT) == [[2]])

        export2_id = self.export_data.create(cursor, USER, {
            'integer': 0,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['integer'], context=CONTEXT) == [[0]])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['integer'], context=CONTEXT) ==
            [[2], [0]])

        cursor.rollback()
        cursor.close()

    def test0030float(self):
        '''
        Test float.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'float': 1.1,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['float'], context=CONTEXT) == [[1.1]])

        export2_id = self.export_data.create(cursor, USER, {
            'float': 0,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['float'], context=CONTEXT) == [[0]])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['float'], context=CONTEXT) ==
            [[1.1], [0]])

        cursor.rollback()
        cursor.close()

    def test0040numeric(self):
        '''
        Test numeric.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'numeric': Decimal('1.1'),
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['numeric'], context=CONTEXT) == [[Decimal('1.1')]])

        export2_id = self.export_data.create(cursor, USER, {
            'numeric': Decimal('0'),
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['numeric'], context=CONTEXT) == [[Decimal('0')]])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['numeric'], context=CONTEXT) ==
            [[Decimal('1.1')], [Decimal('0')]])

        cursor.rollback()
        cursor.close()

    def test0050char(self):
        '''
        Test char.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'char': 'test',
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['char'], context=CONTEXT) == [['test']])

        export2_id = self.export_data.create(cursor, USER, {
            'char': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['char'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['char'], context=CONTEXT) ==
            [['test'], ['']])

        cursor.rollback()
        cursor.close()

    def test0060text(self):
        '''
        Test text.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'text': 'test',
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['text'], context=CONTEXT) == [['test']])

        export2_id = self.export_data.create(cursor, USER, {
            'text': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['text'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['text'], context=CONTEXT) ==
            [['test'], ['']])

        cursor.rollback()
        cursor.close()

    def test0070sha(self):
        '''
        Test sha.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'sha': 'Test',
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['sha'], context=CONTEXT) == [['640ab2bae07bedc4c163f679a746f7ab7fb5d1fa']])

        cursor.rollback()
        cursor.close()

    def test0080date(self):
        '''
        Test date.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'date': datetime.date(2010, 1, 1),
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['date'], context=CONTEXT) == [[datetime.date(2010, 1, 1)]])

        export2_id = self.export_data.create(cursor, USER, {
            'date': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['date'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['date'], context=CONTEXT) ==
            [[datetime.date(2010, 1, 1)], ['']])

        cursor.rollback()
        cursor.close()

    def test0090datetime(self):
        '''
        Test datetime.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'datetime': datetime.datetime(2010, 1, 1, 12, 0, 0),
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['datetime'], context=CONTEXT) == [[datetime.datetime(2010, 1,
                1, 12, 0, 0)]])

        export2_id = self.export_data.create(cursor, USER, {
            'datetime': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['datetime'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['datetime'], context=CONTEXT) ==
            [[datetime.datetime(2010, 1, 1, 12, 0, 0)], ['']])

        cursor.rollback()
        cursor.close()

    def test0100selection(self):
        '''
        Test selection.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {
            'selection': 'select1',
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['selection'], context=CONTEXT) == [['select1']])

        export2_id = self.export_data.create(cursor, USER, {
            'selection': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['selection'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['selection'], context=CONTEXT) ==
            [['select1'], ['']])

        cursor.rollback()
        cursor.close()

    def test0110many2one(self):
        '''
        Test many2one.
        '''
        cursor = DB.cursor()

        target_id = self.export_data_target.create(cursor, USER, {
            'name': 'Target Test',
            }, context=CONTEXT)
        export1_id = self.export_data.create(cursor, USER, {
            'many2one': target_id,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['many2one/name'], context=CONTEXT) == [['Target Test']])

        export2_id = self.export_data.create(cursor, USER, {
            'many2one': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['many2one/name'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['many2one/name'], context=CONTEXT) ==
            [['Target Test'], ['']])

        cursor.rollback()
        cursor.close()

    def test0120many2many(self):
        '''
        Test many2many.
        '''
        cursor = DB.cursor()

        target1_id = self.export_data_target.create(cursor, USER, {
            'name': 'Target 1',
            }, context=CONTEXT)
        export1_id = self.export_data.create(cursor, USER, {
            'many2many': [('set', [target1_id])],
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['many2many/name'], context=CONTEXT) == [['Target 1']])

        target2_id = self.export_data_target.create(cursor, USER, {
            'name': 'Target 2',
            }, context=CONTEXT)
        self.export_data.write(cursor, USER, export1_id, {
            'many2many': [('set', [target1_id, target2_id])],
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['id', 'many2many/name'], context=CONTEXT) ==
            [[export1_id, 'Target 1'], ['', 'Target 2']])

        export2_id = self.export_data.create(cursor, USER, {
            'many2many': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['many2many/name'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['id', 'many2many/name'], context=CONTEXT)
            == [[export1_id, 'Target 1'], ['', 'Target 2'], [export2_id, '']])

        cursor.rollback()
        cursor.close()

    def test0130one2many(self):
        '''
        Test one2many.
        '''
        cursor = DB.cursor()

        export1_id = self.export_data.create(cursor, USER, {}, context=CONTEXT)
        target1_id = self.export_data_target.create(cursor, USER, {
            'name': 'Target 1',
            'one2many': export1_id,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['one2many/name'], context=CONTEXT) == [['Target 1']])

        target2_id = self.export_data_target.create(cursor, USER, {
            'name': 'Target 2',
            'one2many': export1_id,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['id', 'one2many/name'], context=CONTEXT) ==
            [[export1_id, 'Target 1'], ['', 'Target 2']])

        export2_id = self.export_data.create(cursor, USER, {}, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['one2many/name'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['id', 'one2many/name'], context=CONTEXT)
            == [[export1_id, 'Target 1'], ['', 'Target 2'], [export2_id, '']])

        cursor.rollback()
        cursor.close()

    def test0140reference(self):
        '''
        Test reference.
        '''
        cursor = DB.cursor()

        target1_id = self.export_data_target.create(cursor, USER, {},
                context=CONTEXT)
        export1_id = self.export_data.create(cursor, USER, {
            'reference': 'test.export_data.target,%s' % target1_id,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export1_id],
            ['reference'], context=CONTEXT) ==
            [['test.export_data.target,%s' % target1_id]])

        export2_id = self.export_data.create(cursor, USER, {
            'reference': False,
            }, context=CONTEXT)
        self.assert_(self.export_data.export_data(cursor, USER, [export2_id],
            ['reference'], context=CONTEXT) == [['']])

        self.assert_(self.export_data.export_data(cursor, USER,
            [export1_id, export2_id], ['reference'], context=CONTEXT) ==
            [['test.export_data.target,%s' % target1_id], ['']])

        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ExportDataTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
