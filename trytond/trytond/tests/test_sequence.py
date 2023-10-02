# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from trytond.ir.sequence import LastTimestampError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class SequenceTestCase(unittest.TestCase):
    'Test Sequence'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @staticmethod
    def get_model():
        pool = Pool()
        return pool.get('ir.sequence')

    @with_transaction()
    def test_incremental(self):
        'Test incremental'
        pool = Pool()
        Sequence = self.get_model()
        SequenceType = pool.get('ir.sequence.type')

        sequence_type, = SequenceType.search([
                ('name', '=', "Test"),
                ], limit=1)
        sequence, = Sequence.create([{
                    'name': 'Test incremental',
                    'sequence_type': sequence_type.id,
                    'prefix': '',
                    'suffix': '',
                    'type': 'incremental',
                    }])
        self.assertEqual(sequence.number_next, 1)
        self.assertEqual(sequence.preview, '1')
        self.assertEqual(sequence.get(), '1')

        Sequence.write([sequence], {
                'number_increment': 10,
                })
        self.assertEqual(sequence.number_next, 2)
        self.assertEqual(sequence.preview, '2')
        self.assertEqual(sequence.get(), '2')
        self.assertEqual(sequence.preview, '12')
        self.assertEqual(sequence.get(), '12')

        Sequence.write([sequence], {
                'padding': 3,
                })
        self.assertEqual(sequence.number_next, 22)
        self.assertEqual(sequence.preview, '022')
        self.assertEqual(sequence.get(), '022')

    @with_transaction()
    def test_decimal_timestamp(self):
        'Test Decimal Timestamp'
        pool = Pool()
        Sequence = self.get_model()
        SequenceType = pool.get('ir.sequence.type')

        sequence_type, = SequenceType.search([
                ('name', '=', "Test"),
                ], limit=1)
        sequence, = Sequence.create([{
                    'name': 'Test decimal timestamp',
                    'sequence_type': sequence_type.id,
                    'prefix': '',
                    'suffix': '',
                    'type': 'decimal timestamp',
                    }])
        self.assertTrue(sequence.preview)
        timestamp = sequence.get()
        self.assertEqual(timestamp, str(sequence.last_timestamp))

        self.assertEqual(sequence.number_next, None)

        self.assertNotEqual(sequence.get(), timestamp)

        next_timestamp = Sequence._timestamp(sequence)
        self.assertRaises(LastTimestampError, Sequence.write, [sequence], {
                'last_timestamp': next_timestamp + 100,
                })

    @with_transaction()
    def test_hexadecimal_timestamp(self):
        'Test Hexadecimal Timestamp'
        pool = Pool()
        Sequence = self.get_model()
        SequenceType = pool.get('ir.sequence.type')

        sequence_type, = SequenceType.search([
                ('name', '=', "Test"),
                ], limit=1)
        sequence, = Sequence.create([{
                    'name': 'Test hexadecimal timestamp',
                    'sequence_type': sequence_type.id,
                    'prefix': '',
                    'suffix': '',
                    'type': 'hexadecimal timestamp',
                    }])
        self.assertTrue(sequence.preview)
        timestamp = sequence.get()
        self.assertEqual(timestamp,
            hex(int(sequence.last_timestamp))[2:].upper())

        self.assertEqual(sequence.number_next, None)

        self.assertNotEqual(sequence.get(), timestamp)

        next_timestamp = Sequence._timestamp(sequence)
        self.assertRaises(LastTimestampError, Sequence.write, [sequence], {
                'last_timestamp': next_timestamp + 100,
                })

    @with_transaction()
    def test_prefix_suffix(self):
        'Test prefix/suffix'
        pool = Pool()
        Sequence = self.get_model()
        SequenceType = pool.get('ir.sequence.type')

        sequence_type, = SequenceType.search([
                ('name', '=', "Test"),
                ], limit=1)
        sequence, = Sequence.create([{
                    'name': 'Test incremental',
                    'sequence_type': sequence_type.id,
                    'prefix': 'prefix/',
                    'suffix': '/suffix',
                    'type': 'incremental',
                    }])
        self.assertEqual(sequence.preview, 'prefix/1/suffix')
        self.assertEqual(sequence.get(),
            'prefix/1/suffix')

        Sequence.write([sequence], {
                'prefix': '${year}-${month}-${day}/',
                'suffix': '/${day}.${month}.${year}',
                })
        with Transaction().set_context(date=datetime.date(2010, 8, 15)):
            self.assertEqual(
                Sequence(sequence).preview, '2010-08-15/2/15.08.2010')
            self.assertEqual(sequence.get(), '2010-08-15/2/15.08.2010')


class SequenceStrictTestCase(SequenceTestCase):
    "Test Sequence Strict"

    @staticmethod
    def get_model():
        pool = Pool()
        return pool.get('ir.sequence.strict')
