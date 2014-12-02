# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
try:
    import cdecimal
    if 'decimal' not in sys.modules:
        sys.modules['decimal'] = cdecimal
except ImportError:
    import decimal
    sys.modules['cdecimal'] = decimal
import unittest
from decimal import Decimal
import datetime
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class ExportDataTestCase(unittest.TestCase):
    'Test export_data'

    def setUp(self):
        install_module('tests')
        self.export_data = POOL.get('test.export_data')
        self.export_data_target = POOL.get('test.export_data.target')
        self.export_data_relation = POOL.get('test.export_data.relation')

    def test0010boolean(self):
        'Test boolean'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'boolean': True,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['boolean']), [[True]])

            export2, = self.export_data.create([{
                        'boolean': False,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['boolean']),
                [[False]])

            self.assertEqual(
                self.export_data.export_data([export1, export2],
                    ['boolean']),
                [[True], [False]])

            transaction.cursor.rollback()

    def test0020integer(self):
        'Test integer'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'integer': 2,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['integer']), [[2]])

            export2, = self.export_data.create([{
                        'integer': 0,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['integer']), [[0]])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['integer']),
                [[2], [0]])

            transaction.cursor.rollback()

    def test0030float(self):
        'Test float'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'float': 1.1,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['float']), [[1.1]])

            export2, = self.export_data.create([{
                        'float': 0,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['float']), [[0]])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['float']),
                [[1.1], [0]])

            transaction.cursor.rollback()

    def test0040numeric(self):
        'Test numeric'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'numeric': Decimal('1.1'),
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['numeric']),
                [[Decimal('1.1')]])

            export2, = self.export_data.create([{
                        'numeric': Decimal('0'),
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['numeric']),
                [[Decimal('0')]])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['numeric']),
                [[Decimal('1.1')], [Decimal('0')]])

            transaction.cursor.rollback()

    def test0050char(self):
        'Test char'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'char': 'test',
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['char']), [['test']])

            export2, = self.export_data.create([{
                        'char': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['char']), [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['char']),
                [['test'], ['']])

            transaction.cursor.rollback()

    def test0060text(self):
        'Test text'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'text': 'test',
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['text']), [['test']])

            export2, = self.export_data.create([{
                        'text': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['text']), [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['text']),
                [['test'], ['']])

            transaction.cursor.rollback()

    def test0080date(self):
        'Test date'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'date': datetime.date(2010, 1, 1),
                        }])
            self.assert_(self.export_data.export_data([export1],
                ['date']) == [[datetime.date(2010, 1, 1)]])

            export2, = self.export_data.create([{
                        'date': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['date']), [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['date']),
                [[datetime.date(2010, 1, 1)], ['']])

            transaction.cursor.rollback()

    def test0090datetime(self):
        'Test datetime'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'datetime': datetime.datetime(2010, 1, 1, 12, 0, 0),
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['datetime']),
                [[datetime.datetime(2010, 1, 1, 12, 0, 0)]])

            export2, = self.export_data.create([{
                        'datetime': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['datetime']),
                [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['datetime']),
                [[datetime.datetime(2010, 1, 1, 12, 0, 0)], ['']])

            transaction.cursor.rollback()

    def test0100selection(self):
        'Test selection'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{
                        'selection': 'select1',
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['selection',
                        'selection.translated']),
                [['select1', 'Select 1']])

            export2, = self.export_data.create([{
                        'selection': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['selection']), [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2],
                    ['selection']),
                [['select1'], ['']])

            transaction.cursor.rollback()

    def test0110many2one(self):
        'Test many2one'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target, = self.export_data_target.create([{
                        'name': 'Target Test',
                        }])
            export1, = self.export_data.create([{
                        'many2one': target.id,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['many2one/name']),
                [['Target Test']])

            export2, = self.export_data.create([{
                    'many2one': None,
                    }])
            self.assertEqual(
                self.export_data.export_data([export2], ['many2one/name']),
                [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2],
                    ['many2one/name']),
                [['Target Test'], ['']])

            transaction.cursor.rollback()

    def test0120many2many(self):
        'Test many2many'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1, = self.export_data_target.create([{
                        'name': 'Target 1',
                        }])
            export1, = self.export_data.create([{
                        'many2many': [('add', [target1])],
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['many2many/name']),
                [['Target 1']])

            target2, = self.export_data_target.create([{
                        'name': 'Target 2',
                        }])
            self.export_data.write([export1], {
                    'many2many': [('add', [target1.id, target2.id])],
                    })
            self.assertEqual(
                self.export_data.export_data([export1], ['id',
                        'many2many/name']),
                [[export1.id, 'Target 1'], ['', 'Target 2']])

            export2, = self.export_data.create([{
                        'many2many': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['many2many/name']),
                [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2],
                    ['id', 'many2many/name']),
                [[export1.id, 'Target 1'], ['', 'Target 2'], [export2.id, '']])

            transaction.cursor.rollback()

    def test0130one2many(self):
        'Test one2many'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            export1, = self.export_data.create([{}])
            self.export_data_target.create([{
                        'name': 'Target 1',
                        'one2many': export1.id,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['one2many/name']),
                [['Target 1']])

            self.export_data_target.create([{
                        'name': 'Target 2',
                        'one2many': export1.id,
                        }])
            self.assertEqual(
                self.export_data.export_data([export1],
                    ['id', 'one2many/name']),
                [[export1.id, 'Target 1'], ['', 'Target 2']])

            export2, = self.export_data.create([{}])
            self.assertEqual(
                self.export_data.export_data([export2], ['one2many/name']),
                [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2], ['id',
                        'one2many/name']),
                [[export1.id, 'Target 1'], ['', 'Target 2'], [export2.id, '']])

            transaction.cursor.rollback()

    def test0140reference(self):
        'Test reference'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1, = self.export_data_target.create([{}])
            export1, = self.export_data.create([{
                        'reference': str(target1),
                        }])
            self.assertEqual(
                self.export_data.export_data([export1], ['reference']),
                [[str(target1)]])

            export2, = self.export_data.create([{
                        'reference': None,
                        }])
            self.assertEqual(
                self.export_data.export_data([export2], ['reference']), [['']])

            self.assertEqual(
                self.export_data.export_data([export1, export2],
                    ['reference']),
                [[str(target1)], ['']])

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ExportDataTestCase)
