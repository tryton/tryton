#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import datetime
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


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
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'boolean': True,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['boolean']) == [[True]])

            export2_id = self.export_data.create({
                'boolean': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['boolean']) == [[False]])

            self.assert_(self.export_data.export_data( [export1_id,
                export2_id], ['boolean']) == [[True], [False]])

            transaction.cursor.rollback()

    def test0020integer(self):
        '''
        Test integer.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'integer': 2,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['integer']) == [[2]])

            export2_id = self.export_data.create({
                'integer': 0,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['integer']) == [[0]])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['integer']) == [[2], [0]])

            transaction.cursor.rollback()

    def test0030float(self):
        '''
        Test float.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'float': 1.1,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['float']) == [[1.1]])

            export2_id = self.export_data.create({
                'float': 0,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['float']) == [[0]])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['float']) == [[1.1], [0]])

            transaction.cursor.rollback()

    def test0040numeric(self):
        '''
        Test numeric.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'numeric': Decimal('1.1'),
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['numeric']) == [[Decimal('1.1')]])

            export2_id = self.export_data.create({
                'numeric': Decimal('0'),
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['numeric']) == [[Decimal('0')]])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['numeric']) == [[Decimal('1.1')], [Decimal('0')]])

            transaction.cursor.rollback()

    def test0050char(self):
        '''
        Test char.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'char': 'test',
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['char']) == [['test']])

            export2_id = self.export_data.create({
                'char': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['char']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['char']) == [['test'], ['']])

            transaction.cursor.rollback()

    def test0060text(self):
        '''
        Test text.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'text': 'test',
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['text']) == [['test']])

            export2_id = self.export_data.create({
                'text': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['text']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['text']) == [['test'], ['']])

            transaction.cursor.rollback()

    def test0070sha(self):
        '''
        Test sha.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'sha': 'Test',
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['sha']) == [['640ab2bae07bedc4c163f679a746f7ab7fb5d1fa']])

            transaction.cursor.rollback()

    def test0080date(self):
        '''
        Test date.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'date': datetime.date(2010, 1, 1),
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['date']) == [[datetime.date(2010, 1, 1)]])

            export2_id = self.export_data.create({
                'date': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['date']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['date']) == [[datetime.date(2010, 1, 1)], ['']])

            transaction.cursor.rollback()

    def test0090datetime(self):
        '''
        Test datetime.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'datetime': datetime.datetime(2010, 1, 1, 12, 0, 0),
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['datetime']) == [[datetime.datetime(2010, 1, 1, 12, 0, 0)]])

            export2_id = self.export_data.create({
                'datetime': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['datetime']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['datetime']) == [[datetime.datetime(2010, 1, 1, 12, 0, 0)],
                    ['']])

            transaction.cursor.rollback()

    def test0100selection(self):
        '''
        Test selection.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({
                'selection': 'select1',
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['selection']) == [['select1']])

            export2_id = self.export_data.create({
                'selection': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['selection']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['selection']) == [['select1'], ['']])

            transaction.cursor.rollback()

    def test0110many2one(self):
        '''
        Test many2one.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target_id = self.export_data_target.create({
                'name': 'Target Test',
                })
            export1_id = self.export_data.create({
                'many2one': target_id,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['many2one/name']) == [['Target Test']])

            export2_id = self.export_data.create({
                'many2one': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['many2one/name']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['many2one/name']) == [['Target Test'], ['']])

            transaction.cursor.rollback()

    def test0120many2many(self):
        '''
        Test many2many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1_id = self.export_data_target.create({
                'name': 'Target 1',
                })
            export1_id = self.export_data.create({
                'many2many': [('set', [target1_id])],
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['many2many/name']) == [['Target 1']])

            target2_id = self.export_data_target.create({
                'name': 'Target 2',
                })
            self.export_data.write(export1_id, {
                'many2many': [('set', [target1_id, target2_id])],
                })
            self.assert_(self.export_data.export_data([export1_id], ['id',
                'many2many/name']) == [[export1_id, 'Target 1'],
                ['', 'Target 2']])

            export2_id = self.export_data.create({
                'many2many': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['many2many/name']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['id', 'many2many/name']) == [[export1_id, 'Target 1'],
                    ['', 'Target 2'], [export2_id, '']])

            transaction.cursor.rollback()

    def test0130one2many(self):
        '''
        Test one2many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1_id = self.export_data.create({})
            target1_id = self.export_data_target.create({
                'name': 'Target 1',
                'one2many': export1_id,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['one2many/name']) == [['Target 1']])

            target2_id = self.export_data_target.create({
                'name': 'Target 2',
                'one2many': export1_id,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['id', 'one2many/name']) ==
                [[export1_id, 'Target 1'], ['', 'Target 2']])

            export2_id = self.export_data.create({})
            self.assert_(self.export_data.export_data([export2_id],
                ['one2many/name']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['id', 'one2many/name']) == [[export1_id, 'Target 1'],
                    ['', 'Target 2'], [export2_id, '']])

            transaction.cursor.rollback()

    def test0140reference(self):
        '''
        Test reference.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1_id = self.export_data_target.create({})
            export1_id = self.export_data.create({
                'reference': 'test.export_data.target,%s' % target1_id,
                })
            self.assert_(self.export_data.export_data([export1_id],
                ['reference']) ==
                [['test.export_data.target,%s' % target1_id]])

            export2_id = self.export_data.create({
                'reference': False,
                })
            self.assert_(self.export_data.export_data([export2_id],
                ['reference']) == [['']])

            self.assert_(self.export_data.export_data([export1_id, export2_id],
                ['reference']) == [['test.export_data.target,%s' % target1_id],
                    ['']])

            transaction.cursor.rollback()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ExportDataTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
