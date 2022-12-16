# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import datetime
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class SequenceTestCase(unittest.TestCase):
    'Test Sequence'

    def setUp(self):
        install_module('tests')
        self.sequence = POOL.get('ir.sequence')

    def test0010incremental(self):
        'Test incremental'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            sequence, = self.sequence.create([{
                        'name': 'Test incremental',
                        'code': 'test',
                        'prefix': '',
                        'suffix': '',
                        'type': 'incremental',
                        }])
            self.assertEqual(self.sequence.get_id(sequence), '1')

            self.sequence.write([sequence], {
                    'number_increment': 10,
                    })
            self.assertEqual(self.sequence.get_id(sequence), '2')
            self.assertEqual(self.sequence.get_id(sequence), '12')

            self.sequence.write([sequence], {
                    'padding': 3,
                    })
            self.assertEqual(self.sequence.get_id(sequence), '022')

            transaction.cursor.rollback()

    def test0020decimal_timestamp(self):
        'Test Decimal Timestamp'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            sequence, = self.sequence.create([{
                        'name': 'Test decimal timestamp',
                        'code': 'test',
                        'prefix': '',
                        'suffix': '',
                        'type': 'decimal timestamp',
                        }])
            timestamp = self.sequence.get_id(sequence)
            self.assertEqual(timestamp, str(sequence.last_timestamp))

            self.assertNotEqual(self.sequence.get_id(sequence), timestamp)

            next_timestamp = self.sequence._timestamp(sequence)
            self.assertRaises(UserError, self.sequence.write, [sequence], {
                    'last_timestamp': next_timestamp + 100,
                    })

            transaction.cursor.rollback()

    def test0030hexadecimal_timestamp(self):
        'Test Hexadecimal Timestamp'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            sequence, = self.sequence.create([{
                        'name': 'Test hexadecimal timestamp',
                        'code': 'test',
                        'prefix': '',
                        'suffix': '',
                        'type': 'hexadecimal timestamp',
                        }])
            timestamp = self.sequence.get_id(sequence)
            self.assertEqual(timestamp,
                hex(int(sequence.last_timestamp))[2:].upper())

            self.assertNotEqual(self.sequence.get_id(sequence), timestamp)

            next_timestamp = self.sequence._timestamp(sequence)
            self.assertRaises(UserError, self.sequence.write, [sequence], {
                    'last_timestamp': next_timestamp + 100,
                    })

            transaction.cursor.rollback()

    def test0040prefix_suffix(self):
        'Test prefix/suffix'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            sequence, = self.sequence.create([{
                        'name': 'Test incremental',
                        'code': 'test',
                        'prefix': 'prefix/',
                        'suffix': '/suffix',
                        'type': 'incremental',
                        }])
            self.assertEqual(self.sequence.get_id(sequence),
                'prefix/1/suffix')

            self.sequence.write([sequence], {
                    'prefix': '${year}-${month}-${day}/',
                    'suffix': '/${day}.${month}.${year}',
                    })
            with Transaction().set_context(date=datetime.date(2010, 8, 15)):
                self.assertEqual(self.sequence.get_id(sequence),
                    '2010-08-15/2/15.08.2010')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(SequenceTestCase)
