#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.protocols.datatype import Float


class FieldsTestCase(unittest.TestCase):
    '''
    Test Fields.
    '''

    def setUp(self):
        install_module('test')
        self.boolean = POOL.get('test.boolean')
        self.boolean_default = POOL.get('test.boolean_default')

        self.integer = POOL.get('test.integer')
        self.integer_default = POOL.get('test.integer_default')
        self.integer_required = POOL.get('test.integer_required')

        self.float = POOL.get('test.float')
        self.float_default = POOL.get('test.float_default')
        self.float_required = POOL.get('test.float_required')
        self.float_digits = POOL.get('test.float_digits')

        self.numeric = POOL.get('test.numeric')
        self.numeric_default = POOL.get('test.numeric_default')
        self.numeric_required = POOL.get('test.numeric_required')
        self.numeric_digits = POOL.get('test.numeric_digits')

        self.char = POOL.get('test.char')
        self.char_default = POOL.get('test.char_default')
        self.char_required = POOL.get('test.char_required')
        self.char_size = POOL.get('test.char_size')
        self.char_translate = POOL.get('test.char_translate')

        self.text = POOL.get('test.text')
        self.text_default = POOL.get('test.text_default')
        self.text_required = POOL.get('test.text_required')
        self.text_size = POOL.get('test.text_size')
        self.text_translate = POOL.get('test.text_translate')

        self.sha = POOL.get('test.sha')
        self.sha_default = POOL.get('test.sha_default')
        self.sha_required = POOL.get('test.sha_required')

        self.date = POOL.get('test.date')
        self.date_default = POOL.get('test.date_default')
        self.date_required = POOL.get('test.date_required')

        self.datetime = POOL.get('test.datetime')
        self.datetime_default = POOL.get('test.datetime_default')
        self.datetime_required = POOL.get('test.datetime_required')

        self.one2one = POOL.get('test.one2one')
        self.one2one_target = POOL.get('test.one2one.target')
        self.one2one_required = POOL.get('test.one2one_required')

        self.property_ = POOL.get('test.property')

    def test0010boolean(self):
        '''
        Test Boolean.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            boolean1_id = self.boolean.create({
                'boolean': True,
                })
            self.assert_(boolean1_id)

            boolean1 = self.boolean.read(boolean1_id, ['boolean'])
            self.assert_(boolean1['boolean'] == True)

            boolean_ids = self.boolean.search([
                ('boolean', '=', True),
                ])
            self.assert_(boolean_ids == [boolean1_id])

            boolean_ids = self.boolean.search([
                ('boolean', '!=', True),
                ])
            self.assert_(boolean_ids == [])

            boolean_ids = self.boolean.search([
                ('boolean', 'in', [True]),
                ])
            self.assert_(boolean_ids == [boolean1_id])

            boolean_ids = self.boolean.search([
                ('boolean', 'in', [False]),
                ])
            self.assert_(boolean_ids == [])

            boolean_ids = self.boolean.search([
                ('boolean', 'not in', [True]),
                ])
            self.assert_(boolean_ids == [])

            boolean_ids = self.boolean.search([
                ('boolean', 'not in', [False]),
                ])
            self.assert_(boolean_ids == [boolean1_id])

            boolean2_id = self.boolean.create({
                'boolean': False,
                })
            self.assert_(boolean2_id)

            boolean2 = self.boolean.read(boolean2_id, ['boolean'])
            self.assert_(boolean2['boolean'] == False)

            boolean_ids = self.boolean.search([
                ('boolean', '=', False),
                ])
            self.assert_(boolean_ids == [boolean2_id])

            boolean_ids = self.boolean.search([
                ('boolean', 'in', [True, False]),
                ])
            self.assert_(boolean_ids == [boolean1_id, boolean2_id])

            boolean_ids = self.boolean.search([
                ('boolean', 'not in', [True, False]),
                ])
            self.assert_(boolean_ids == [])

            boolean3_id = self.boolean.create({})
            self.assert_(boolean3_id)

            # Test search with NULL value
            boolean4_id = self.boolean.create({
                    'boolean': None,
                    })
            self.assert_(boolean4_id)

            boolean_ids = self.boolean.search([
                    ('boolean', '=', False),
                    ])
            self.assertEqual(boolean_ids,
                [boolean2_id, boolean3_id, boolean4_id])

            boolean_ids = self.boolean.search([
                    ('boolean', '!=', False),
                    ])
            self.assertEqual(boolean_ids, [boolean1_id])

            boolean3 = self.boolean.read(boolean3_id, ['boolean'])
            self.assert_(boolean3['boolean'] == False)

            boolean4_id = self.boolean_default.create({})
            self.assert_(boolean4_id)

            boolean4 = self.boolean_default.read(boolean4_id, ['boolean'])
            self.assert_(boolean4['boolean'] == True)

            self.boolean.write(boolean1_id, {
                'boolean': False,
                })
            boolean1 = self.boolean.read(boolean1_id, ['boolean'])
            self.assert_(boolean1['boolean'] == False)

            self.boolean.write(boolean2_id, {
                'boolean': True,
                })
            boolean2 = self.boolean.read(boolean2_id, ['boolean'])
            self.assert_(boolean2['boolean'] == True)

            transaction.cursor.rollback()

    def test0020integer(self):
        '''
        Test Integer.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            integer1_id = self.integer.create({
                'integer': 1,
                })
            self.assert_(integer1_id)

            integer1 = self.integer.read(integer1_id, ['integer'])
            self.assert_(integer1['integer'] == 1)

            integer_ids = self.integer.search([
                ('integer', '=', 1),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '=', 0),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '!=', 1),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '!=', 0),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', 'in', [1]),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', 'in', [0]),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', 'in', []),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', 'not in', [1]),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', 'not in', [0]),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', 'not in', []),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '<', 5),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '<', -5),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '<', 1),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '<=', 5),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '<=', -5),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '<=', 1),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '>', 5),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '>', -5),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '>', 1),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '>=', 5),
                ])
            self.assert_(integer_ids == [])

            integer_ids = self.integer.search([
                ('integer', '>=', -5),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer_ids = self.integer.search([
                ('integer', '>=', 1),
                ])
            self.assert_(integer_ids == [integer1_id])

            integer2_id = self.integer.create({
                'integer': 0,
                })
            self.assert_(integer2_id)

            integer2 = self.integer.read(integer2_id, ['integer'])
            self.assert_(integer2['integer'] == 0)

            integer_ids = self.integer.search([
                ('integer', '=', 0),
                ])
            self.assert_(integer_ids == [integer2_id])

            integer_ids = self.integer.search([
                ('integer', 'in', [0, 1]),
                ])
            self.assert_(integer_ids == [integer1_id, integer2_id])

            integer_ids = self.integer.search([
                ('integer', 'not in', [0, 1]),
                ])
            self.assert_(integer_ids == [])

            integer3_id = self.integer.create({})
            self.assert_(integer3_id)

            integer3 = self.integer.read(integer3_id, ['integer'])
            self.assert_(integer3['integer'] == 0)

            integer4_id = self.integer_default.create({})
            self.assert_(integer4_id)

            integer4 = self.integer_default.read(integer4_id, ['integer'])
            self.assert_(integer4['integer'] == 5)

            self.integer.write(integer1_id, {
                'integer': 0,
                })
            integer1 = self.integer.read(integer1_id, ['integer'])
            self.assert_(integer1['integer'] == 0)

            self.integer.write(integer2_id, {
                'integer': 1,
                })
            integer2 = self.integer.read(integer2_id, ['integer'])
            self.assert_(integer2['integer'] == 1)

            self.failUnlessRaises(Exception, self.integer.create, {
                'integer': 'test',
                })

            self.failUnlessRaises(Exception, self.integer.write, integer1_id, {
                'integer': 'test',
                })

            integer5_id = self.integer_required.create({})
            self.assert_(integer5_id)

            integer5 = self.integer_required.read(integer5_id, ['integer'])
            self.assert_(integer5['integer'] == 0)

            transaction.cursor.rollback()

    def test0030float(self):
        '''
        Test Float.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            float1_id = self.float.create({
                'float': 1.1,
                })
            self.assert_(float1_id)

            float1 = self.float.read(float1_id, ['float'])
            self.assert_(float1['float'] == 1.1)

            float_ids = self.float.search([
                ('float', '=', 1.1),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '=', 0),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '!=', 1.1),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '!=', 0),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', 'in', [1.1]),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', 'in', [0]),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', 'in', []),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', 'not in', [1.1]),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', 'not in', [0]),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', 'not in', []),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '<', 5),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '<', -5),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '<', 1.1),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '<=', 5),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '<=', -5),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '<=', 1.1),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '>', 5),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '>', -5),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '>', 1.1),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '>=', 5),
                ])
            self.assert_(float_ids == [])

            float_ids = self.float.search([
                ('float', '>=', -5),
                ])
            self.assert_(float_ids == [float1_id])

            float_ids = self.float.search([
                ('float', '>=', 1.1),
                ])
            self.assert_(float_ids == [float1_id])

            float2_id = self.float.create({
                'float': 0,
                })
            self.assert_(float2_id)

            float2 = self.float.read(float2_id, ['float'])
            self.assert_(float2['float'] == 0)

            float_ids = self.float.search([
                ('float', '=', 0),
                ])
            self.assert_(float_ids == [float2_id])

            float_ids = self.float.search([
                ('float', 'in', [0, 1.1]),
                ])
            self.assert_(float_ids == [float1_id, float2_id])

            float_ids = self.float.search([
                ('float', 'not in', [0, 1.1]),
                ])
            self.assert_(float_ids == [])

            float3_id = self.float.create({})
            self.assert_(float3_id)

            float3 = self.float.read(float3_id, ['float'])
            self.assert_(float3['float'] == 0)

            float4_id = self.float_default.create({})
            self.assert_(float4_id)

            float4 = self.float_default.read(float4_id, ['float'])
            self.assert_(float4['float'] == 5.5)

            self.float.write(float1_id, {
                'float': 0,
                })
            float1 = self.float.read(float1_id, ['float'])
            self.assert_(float1['float'] == 0)

            self.float.write(float2_id, {
                'float': 1.1,
                })
            float2 = self.float.read(float2_id, ['float'])
            self.assert_(float2['float'] == 1.1)

            self.failUnlessRaises(Exception, self.float.create, {
                'float': 'test',
                })

            self.failUnlessRaises(Exception, self.float.write, float1_id, {
                'float': 'test',
                })

            float5_id = self.float_required.create({})
            self.assert_(float5_id)

            float5 = self.float_required.read(float5_id, ['float'])
            self.assert_(float5['float'] == 0)

            float6_id = self.float_digits.create({
                'digits': 1,
                'float': 1.1,
                })
            self.assert_(float6_id)

            self.failUnlessRaises(Exception, self.float_digits.create, {
                'digits': 1,
                'float': 1.11,
                })

            self.failUnlessRaises(Exception, self.float_digits.write, float6_id, {
                'float': 1.11,
                })

            self.failUnlessRaises(Exception, self.float_digits.write, float6_id, {
                'digits': 0,
                })

            float7_id = self.float.create({
                'float': 0.123456789012345,
                })

            float7 = self.float.read(float7_id, ['float'])
            self.assert_(float7['float'] == 0.123456789012345)

            float8_id = self.float.create({
                'float': Float('1.1'),
                })

            float8 = self.float.read(float8_id, ['float'])
            self.assertEqual(float8['float'], 1.1)

            transaction.cursor.rollback()

    def test0040numeric(self):
        '''
        Test Numeric.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            numeric1_id = self.numeric.create({
                'numeric': Decimal('1.1'),
                })
            self.assert_(numeric1_id)

            numeric1 = self.numeric.read(numeric1_id, ['numeric'])
            self.assert_(numeric1['numeric'] == Decimal('1.1'))

            numeric_ids = self.numeric.search([
                ('numeric', '=', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '=', Decimal('0')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '!=', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '!=', Decimal('0')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', 'in', [Decimal('1.1')]),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', 'in', [Decimal('0')]),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', 'in', []),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', 'not in', [Decimal('1.1')]),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', 'not in', [Decimal('0')]),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', 'not in', []),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '<', Decimal('5')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '<', Decimal('-5')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '<', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '<=', Decimal('5')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '<=', Decimal('-5')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '<=', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '>', Decimal('5')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '>', Decimal('-5')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '>', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '>=', Decimal('5')),
                ])
            self.assert_(numeric_ids == [])

            numeric_ids = self.numeric.search([
                ('numeric', '>=', Decimal('-5')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric_ids = self.numeric.search([
                ('numeric', '>=', Decimal('1.1')),
                ])
            self.assert_(numeric_ids == [numeric1_id])

            numeric2_id = self.numeric.create({
                'numeric': Decimal('0'),
                })
            self.assert_(numeric2_id)

            numeric2 = self.numeric.read(numeric2_id, ['numeric'])
            self.assert_(numeric2['numeric'] == Decimal('0'))

            numeric_ids = self.numeric.search([
                ('numeric', '=', Decimal('0')),
                ])
            self.assert_(numeric_ids == [numeric2_id])

            numeric_ids = self.numeric.search([
                ('numeric', 'in', [Decimal('0'), Decimal('1.1')]),
                ])
            self.assert_(numeric_ids == [numeric1_id, numeric2_id])

            numeric_ids = self.numeric.search([
                ('numeric', 'not in', [Decimal('0'), Decimal('1.1')]),
                ])
            self.assert_(numeric_ids == [])

            numeric3_id = self.numeric.create({})
            self.assert_(numeric3_id)

            numeric3 = self.numeric.read(numeric3_id, ['numeric'])
            self.assert_(numeric3['numeric'] == Decimal('0'))

            numeric4_id = self.numeric_default.create({})
            self.assert_(numeric4_id)

            numeric4 = self.numeric_default.read(numeric4_id, ['numeric'])
            self.assert_(numeric4['numeric'] == Decimal('5.5'))

            self.numeric.write(numeric1_id, {
                'numeric': Decimal('0'),
                })
            numeric1 = self.numeric.read(numeric1_id, ['numeric'])
            self.assert_(numeric1['numeric'] == Decimal('0'))

            self.numeric.write(numeric2_id, {
                'numeric': Decimal('1.1'),
                })
            numeric2 = self.numeric.read(numeric2_id, ['numeric'])
            self.assert_(numeric2['numeric'] == Decimal('1.1'))

            self.failUnlessRaises(Exception, self.numeric.create, {
                'numeric': 'test',
                })

            self.failUnlessRaises(Exception, self.numeric.write, numeric1_id, {
                'numeric': 'test',
                })

            numeric5_id = self.numeric_required.create({})
            self.assert_(numeric5_id)

            numeric5 = self.numeric_required.read(numeric5_id, ['numeric'])
            self.assert_(numeric5['numeric'] == Decimal('0'))

            numeric6_id = self.numeric_digits.create({
                'digits': 1,
                'numeric': Decimal('1.1'),
                })
            self.assert_(numeric6_id)

            self.failUnlessRaises(Exception, self.numeric_digits.create, {
                'digits': 1,
                'numeric': Decimal('1.11'),
                })

            self.failUnlessRaises(Exception, self.numeric_digits.write,
                    numeric6_id, {
                        'numeric': Decimal('1.11'),
                        })

            self.failUnlessRaises(Exception, self.numeric_digits.write,
                    numeric6_id, {
                        'numeric': Decimal('0.10000000000000001'),
                        })

            self.failUnlessRaises(Exception, self.numeric_digits.write,
                    numeric6_id, {
                        'digits': 0,
                        })

            numeric7_id = self.numeric.create({
                'numeric': Decimal('0.1234567890123456789'),
                })

            numeric7 = self.numeric.read(numeric7_id, ['numeric'])
            self.assert_(numeric7['numeric'] ==
                    Decimal('0.1234567890123456789'))

            numeric8_id = self.numeric.create({
                'numeric': Float('1.1'),
                })

            numeric8 = self.numeric.read(numeric8_id, ['numeric'])
            self.assertEqual(numeric8['numeric'], Decimal('1.1'))

            transaction.cursor.rollback()

    def test0050char(self):
        '''
        Test Char.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for char in (self.char, self.char_translate):
                char1_id = char.create({
                    'char': 'Test',
                    })
                self.assert_(char1_id)

                char1 = char.read(char1_id, ['char'])
                self.assert_(char1['char'] == 'Test')

                char_ids = char.search([
                    ('char', '=', 'Test'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', '=', 'Foo'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', '=', False),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', '!=', 'Test'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', '!=', 'Foo'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', '!=', False),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'in', ['Test']),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'in', ['Foo']),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'in', [False]),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'in', []),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not in', ['Test']),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not in', ['Foo']),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'not in', [False]),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'not in', []),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'like', 'Test'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'like', 'T%'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'like', 'Foo'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'like', 'F%'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'ilike', 'test'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'ilike', 't%'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'ilike', 'foo'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'ilike', 'f%'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not like', 'Test'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not like', 'T%'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not like', 'Foo'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'not like', 'F%'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'not ilike', 'test'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not ilike', 't%'),
                    ])
                self.assert_(char_ids == [])

                char_ids = char.search([
                    ('char', 'not ilike', 'foo'),
                    ])
                self.assert_(char_ids == [char1_id])

                char_ids = char.search([
                    ('char', 'not ilike', 'f%'),
                    ])
                self.assert_(char_ids == [char1_id])

                char2_id = char.create({
                    'char': False,
                    })
                self.assert_(char2_id)

                char2 = char.read(char2_id, ['char'])
                self.assert_(char2['char'] == None)

                char_ids = char.search([
                    ('char', '=', False),
                    ])
                self.assert_(char_ids == [char2_id])

                char_ids = char.search([
                    ('char', 'in', [False, 'Test']),
                    ])
                self.assert_(char_ids == [char1_id, char2_id])

                char_ids = char.search([
                    ('char', 'not in', [False, 'Test']),
                    ])
                self.assert_(char_ids == [])

            char3_id = self.char.create({})
            self.assert_(char3_id)

            char3 = self.char.read(char3_id, ['char'])
            self.assert_(char3['char'] == None)

            char4_id = self.char_default.create({})
            self.assert_(char4_id)

            char4 = self.char_default.read(char4_id, ['char'])
            self.assert_(char4['char'] == 'Test')

            self.char.write(char1_id, {
                'char': False,
                })
            char1 = self.char.read(char1_id, ['char'])
            self.assert_(char1['char'] == None)

            self.char.write(char2_id, {
                'char': 'Test',
                })
            char2 = self.char.read(char2_id, ['char'])
            self.assert_(char2['char'] == 'Test')

            self.failUnlessRaises(Exception, self.char_required.create, {})
            transaction.cursor.rollback()

            char5_id = self.char_required.create({
                'char': 'Test',
                })
            self.assert_(char5_id)

            char6_id = self.char_size.create({
                'char': 'Test',
                })
            self.assert_(char6_id)

            self.failUnlessRaises(Exception, self.char_size.create, {
                'char': 'foobar',
                })

            self.failUnlessRaises(Exception, self.char_size.write, char6_id, {
                'char': 'foobar',
                })
            transaction.cursor.rollback()

            char7_id = self.char.create({
                'char': u'é',
                })
            self.assert_(char7_id)

            char7 = self.char.read(char7_id, ['char'])
            self.assert_(char7['char'] == u'é')

            char_ids = self.char.search([
                ('char', '=', u'é'),
                ])
            self.assert_(char_ids == [char7_id])

            self.char.write(char7_id, {
                'char': 'é',
                })
            char7 = self.char.read(char7_id, ['char'])
            self.assert_(char7['char'] == u'é')

            char_ids = self.char.search([
                ('char', '=', 'é'),
                ])
            self.assert_(char_ids == [char7_id])

            transaction.cursor.rollback()

    def test0060text(self):
        '''
        Test Text.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for text in (self.text, self.text_translate):
                text1_id = text.create({
                    'text': 'Test',
                    })
                self.assert_(text1_id)

                text1 = text.read(text1_id, ['text'])
                self.assert_(text1['text'] == 'Test')

                text_ids = text.search([
                    ('text', '=', 'Test'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', '=', 'Foo'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', '=', False),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', '!=', 'Test'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', '!=', 'Foo'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', '!=', False),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'in', ['Test']),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'in', ['Foo']),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'in', [False]),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'in', []),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not in', ['Test']),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not in', ['Foo']),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'not in', [False]),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'not in', []),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'like', 'Test'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'like', 'T%'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'like', 'Foo'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'like', 'F%'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'ilike', 'test'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'ilike', 't%'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'ilike', 'foo'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'ilike', 'f%'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not like', 'Test'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not like', 'T%'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not like', 'Foo'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'not like', 'F%'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'not ilike', 'test'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not ilike', 't%'),
                    ])
                self.assert_(text_ids == [])

                text_ids = text.search([
                    ('text', 'not ilike', 'foo'),
                    ])
                self.assert_(text_ids == [text1_id])

                text_ids = text.search([
                    ('text', 'not ilike', 'f%'),
                    ])
                self.assert_(text_ids == [text1_id])

                text2_id = text.create({
                    'text': False,
                    })
                self.assert_(text2_id)

                text2 = text.read(text2_id, ['text'])
                self.assert_(text2['text'] == None)

                text_ids = text.search([
                    ('text', '=', False),
                    ])
                self.assert_(text_ids == [text2_id])

                text_ids = text.search([
                    ('text', 'in', [False, 'Test']),
                    ])
                self.assert_(text_ids == [text1_id, text2_id])

                text_ids = text.search([
                    ('text', 'not in', [False, 'Test']),
                    ])
                self.assert_(text_ids == [])

            text3_id = self.text.create({})
            self.assert_(text3_id)

            text3 = self.text.read(text3_id, ['text'])
            self.assert_(text3['text'] == None)

            text4_id = self.text_default.create({})
            self.assert_(text4_id)

            text4 = self.text_default.read(text4_id, ['text'])
            self.assert_(text4['text'] == 'Test')

            self.text.write(text1_id, {
                'text': False,
                })
            text1 = self.text.read(text1_id, ['text'])
            self.assert_(text1['text'] == None)

            self.text.write(text2_id, {
                'text': 'Test',
                })
            text2 = self.text.read(text2_id, ['text'])
            self.assert_(text2['text'] == 'Test')

            self.failUnlessRaises(Exception, self.text_required.create, {})
            transaction.cursor.rollback()

            text5_id = self.text_required.create({
                'text': 'Test',
                })
            self.assert_(text5_id)

            text6_id = self.text_size.create({
                'text': 'Test',
                })
            self.assert_(text6_id)

            self.failUnlessRaises(Exception, self.text_size.create, {
                'text': 'foobar',
                })

            self.failUnlessRaises(Exception, self.text_size.write, text6_id, {
                'text': 'foobar',
                })

            text7_id = self.text.create({
                'text': 'Foo\nBar',
                })
            self.assert_(text7_id)

            text8_id = self.text.create({
                'text': u'é',
                })
            self.assert_(text8_id)

            text8 = self.text.read(text8_id, ['text'])
            self.assert_(text8['text'] == u'é')

            text_ids = self.text.search([
                ('text', '=', u'é'),
                ])
            self.assert_(text_ids == [text8_id])

            self.text.write(text8_id, {
                'text': 'é',
                })
            text8 = self.text.read(text8_id, ['text'])
            self.assert_(text8['text'] == u'é')

            text_ids = self.text.search([
                ('text', '=', 'é'),
                ])
            self.assert_(text_ids == [text8_id])

            transaction.cursor.rollback()

    def test0070sha(self):
        '''
        Test Sha.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            sha1_id = self.sha.create({
                'sha': 'Test',
                })
            self.assert_(sha1_id)

            sha1 = self.sha.read(sha1_id, ['sha'])
            self.assert_(sha1['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

            sha_ids = self.sha.search([
                ('sha', '=', 'Test'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', '=', 'Foo'),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', '=', False),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', '!=', 'Test'),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', '!=', 'Foo'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', '!=', False),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'in', ['Test']),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'in', ['Foo']),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'in', [False]),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'in', []),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'not in', ['Test']),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'not in', ['Foo']),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'not in', [False]),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'not in', []),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'like', 'Test'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'like', 'Foo'),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'ilike', 'Test'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'ilike', 'foo'),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'not like', 'Test'),
                ])
            self.assert_(sha_ids == [])

            sha_ids = self.sha.search([
                ('sha', 'not like', 'Foo'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha_ids = self.sha.search([
                ('sha', 'not ilike', 'foo'),
                ])
            self.assert_(sha_ids == [sha1_id])

            sha2_id = self.sha.create({
                'sha': False,
                })
            self.assert_(sha2_id)

            sha2 = self.sha.read(sha2_id, ['sha'])
            self.assert_(sha2['sha'] == None)

            sha_ids = self.sha.search([
                ('sha', '=', False),
                ])
            self.assert_(sha_ids == [sha2_id])

            sha_ids = self.sha.search([
                ('sha', 'in', [False, 'Test']),
                ])
            self.assert_(sha_ids == [sha1_id, sha2_id])

            sha_ids = self.sha.search([
                ('sha', 'not in', [False, 'Test']),
                ])
            self.assert_(sha_ids == [])

            sha3_id = self.sha.create({})
            self.assert_(sha3_id)

            sha3 = self.sha.read(sha3_id, ['sha'])
            self.assert_(sha3['sha'] == None)

            sha4_id = self.sha_default.create({})
            self.assert_(sha4_id)

            sha4 = self.sha_default.read(sha4_id, ['sha'])
            self.assert_(sha4['sha'] == 'ba79baeb9f10896a46ae74715271b7f586e74640')

            self.sha.write(sha1_id, {
                'sha': False,
                })
            sha1 = self.sha.read(sha1_id, ['sha'])
            self.assert_(sha1['sha'] == None)

            self.sha.write(sha2_id, {
                'sha': 'Test',
                })
            sha2 = self.sha.read(sha2_id, ['sha'])
            self.assert_(sha2['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

            self.failUnlessRaises(Exception, self.sha_required.create, {})
            transaction.cursor.rollback()

            sha5_id = self.sha_required.create({
                'sha': 'Test',
                })
            self.assert_(sha5_id)

            sha6_id = self.sha.create({
                'sha': u'é',
                })
            self.assert_(sha6_id)

            sha6 = self.sha.read(sha6_id, ['sha'])
            self.assert_(sha6['sha'] ==
                    u'bf15be717ac1b080b4f1c456692825891ff5073d')

            sha_ids = self.sha.search([
                ('sha', '=', u'é'),
                ])
            self.assert_(sha_ids == [sha6_id])

            self.sha.write(sha6_id, {
                'sha': 'é',
                })
            sha6 = self.sha.read(sha6_id, ['sha'])
            self.assert_(sha6['sha'] ==
                    u'bf15be717ac1b080b4f1c456692825891ff5073d')

            sha_ids = self.sha.search([
                ('sha', '=', 'é'),
                ])
            self.assert_(sha_ids == [sha6_id])

            transaction.cursor.rollback()

    def test0080date(self):
        '''
        Test Date.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            today = datetime.date(2009, 1, 1)
            tomorrow = today + datetime.timedelta(1)
            yesterday = today - datetime.timedelta(1)
            default_date = datetime.date(2000, 1, 1)

            date1_id = self.date.create({
                'date': today,
                })
            self.assert_(date1_id)

            date1 = self.date.read(date1_id, ['date'])
            self.assert_(date1['date'] == today)

            date_ids = self.date.search([
                ('date', '=', today),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '=', tomorrow),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '=', False),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '!=', today),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '!=', tomorrow),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '!=', False),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', 'in', [today]),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', 'in', [tomorrow]),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', 'in', [False]),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', 'in', []),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', 'not in', [today]),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', 'not in', [tomorrow]),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', 'not in', [False]),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', 'not in', []),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '<', tomorrow),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '<', yesterday),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '<', today),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '<=', today),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '<=', yesterday),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '<=', tomorrow),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '>', tomorrow),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '>', yesterday),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '>', today),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '>=', tomorrow),
                ])
            self.assert_(date_ids == [])

            date_ids = self.date.search([
                ('date', '>=', yesterday),
                ])
            self.assert_(date_ids == [date1_id])

            date_ids = self.date.search([
                ('date', '>=', today),
                ])
            self.assert_(date_ids == [date1_id])

            date2_id = self.date.create({
                'date': yesterday,
                })
            self.assert_(date2_id)

            date2 = self.date.read(date2_id, ['date'])
            self.assert_(date2['date'] == yesterday)

            date_ids = self.date.search([
                ('date', '=', yesterday),
                ])
            self.assert_(date_ids == [date2_id])

            date_ids = self.date.search([
                ('date', 'in', [yesterday, today]),
                ])
            self.assert_(date_ids == [date1_id, date2_id])

            date_ids = self.date.search([
                ('date', 'not in', [yesterday, today]),
                ])
            self.assert_(date_ids == [])

            date3_id = self.date.create({})
            self.assert_(date3_id)

            date3 = self.date.read(date3_id, ['date'])
            self.assert_(date3['date'] == None)

            date4_id = self.date_default.create({})
            self.assert_(date4_id)

            date4 = self.date_default.read(date4_id, ['date'])
            self.assert_(date4['date'] == default_date)

            self.date.write(date1_id, {
                'date': yesterday,
                })
            date1 = self.date.read(date1_id, ['date'])
            self.assert_(date1['date'] == yesterday)

            self.date.write(date2_id, {
                'date': today,
                })
            date2 = self.date.read(date2_id, ['date'])
            self.assert_(date2['date'] == today)

            self.failUnlessRaises(Exception, self.date.create, {
                'date': 'test',
                })

            self.failUnlessRaises(Exception, self.date.write, date1_id, {
                'date': 'test',
                })

            self.failUnlessRaises(Exception, self.date.create, {
                'date': 1,
                })

            self.failUnlessRaises(Exception, self.date.write, date1_id, {
                'date': 1,
                })

            self.failUnlessRaises(Exception, self.date.create, {
                'date': datetime.datetime.now(),
                })

            self.failUnlessRaises(Exception, self.date.write, date1_id, {
                'date': datetime.datetime.now(),
                })

            self.failUnlessRaises(Exception, self.date.create, {
                'date': '2009-13-01',
                })

            self.failUnlessRaises(Exception, self.date.write, date1_id, {
                'date': '2009-02-29',
                })

            date5_id = self.date.create({
                'date': '2009-01-01',
                })
            self.assert_(date5_id)
            date5 = self.date.read(date5_id, ['date'])
            self.assert_(date5['date'] == datetime.date(2009, 1, 1))

            self.failUnlessRaises(Exception, self.date_required.create, {})
            transaction.cursor.rollback()

            date6_id = self.date_required.create({
                'date': today,
                })
            self.assert_(date6_id)

            date7_id = self.date.create({
                'date': None,
                })
            self.assert_(date7_id)

            date8_id = self.date.create({
                'date': False,
                })
            self.assert_(date8_id)

            transaction.cursor.rollback()

    def test0090datetime(self):
        '''
        Test DateTime.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            today = datetime.datetime(2009, 1, 1, 12, 0, 0)
            tomorrow = today + datetime.timedelta(1)
            yesterday = today - datetime.timedelta(1)
            default_datetime = datetime.datetime(2000, 1, 1, 12, 0, 0)

            datetime1_id = self.datetime.create({
                'datetime': today,
                })
            self.assert_(datetime1_id)

            datetime1 = self.datetime.read(datetime1_id, ['datetime'])
            self.assert_(datetime1['datetime'] == today)

            datetime_ids = self.datetime.search([
                ('datetime', '=', today),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '=', tomorrow),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '=', False),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '!=', today),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '!=', tomorrow),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '!=', False),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'in', [today]),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'in', [tomorrow]),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', 'in', [False]),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', 'in', []),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', 'not in', [today]),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', 'not in', [tomorrow]),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'not in', [False]),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'not in', []),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '<', tomorrow),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '<', yesterday),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '<', today),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '<=', today),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '<=', yesterday),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '<=', tomorrow),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '>', tomorrow),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '>', yesterday),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '>', today),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '>=', tomorrow),
                ])
            self.assert_(datetime_ids == [])

            datetime_ids = self.datetime.search([
                ('datetime', '>=', yesterday),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime_ids = self.datetime.search([
                ('datetime', '>=', today),
                ])
            self.assert_(datetime_ids == [datetime1_id])

            datetime2_id = self.datetime.create({
                'datetime': yesterday,
                })
            self.assert_(datetime2_id)

            datetime2 = self.datetime.read(datetime2_id, ['datetime'])
            self.assert_(datetime2['datetime'] == yesterday)

            datetime_ids = self.datetime.search([
                ('datetime', '=', yesterday),
                ])
            self.assert_(datetime_ids == [datetime2_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'in', [yesterday, today]),
                ])
            self.assert_(datetime_ids == [datetime1_id, datetime2_id])

            datetime_ids = self.datetime.search([
                ('datetime', 'not in', [yesterday, today]),
                ])
            self.assert_(datetime_ids == [])

            datetime3_id = self.datetime.create({})
            self.assert_(datetime3_id)

            datetime3 = self.datetime.read(datetime3_id, ['datetime'])
            self.assert_(datetime3['datetime'] == None)

            datetime4_id = self.datetime_default.create({})
            self.assert_(datetime4_id)

            datetime4 = self.datetime_default.read(datetime4_id, ['datetime'])
            self.assert_(datetime4['datetime'] == default_datetime)

            self.datetime.write(datetime1_id, {
                'datetime': yesterday,
                })
            datetime1 = self.datetime.read(datetime1_id, ['datetime'])
            self.assert_(datetime1['datetime'] == yesterday)

            self.datetime.write(datetime2_id, {
                'datetime': today,
                })
            datetime2 = self.datetime.read(datetime2_id, ['datetime'])
            self.assert_(datetime2['datetime'] == today)

            self.failUnlessRaises(Exception, self.datetime.create, {
                'datetime': 'test',
                })

            self.failUnlessRaises(Exception, self.datetime.write, datetime1_id,
                    {
                        'datetime': 'test',
                    })

            self.failUnlessRaises(Exception, self.datetime.create, {
                'datetime': 1,
                })

            self.failUnlessRaises(Exception, self.datetime.write, datetime1_id,
                    {
                        'datetime': 1,
                    })

            self.failUnlessRaises(Exception, self.datetime.create, {
                'datetime': datetime.date.today(),
                })

            self.failUnlessRaises(Exception, self.datetime.write, datetime1_id,
                    {
                        'datetime': datetime.date.today(),
                    })

            self.failUnlessRaises(Exception, self.datetime.create, {
                'datetime': '2009-13-01 12:30:00',
                })

            self.failUnlessRaises(Exception, self.datetime.write, datetime1_id,
                    {
                        'datetime': '2009-02-29 12:30:00',
                    })

            self.failUnlessRaises(Exception, self.datetime.write, datetime1_id,
                    {
                        'datetime': '2009-01-01 25:00:00',
                    })

            datetime5_id = self.datetime.create({
                'datetime': '2009-01-01 12:00:00',
                })
            self.assert_(datetime5_id)
            datetime5 = self.datetime.read(datetime5_id, ['datetime'])
            self.assert_(datetime5['datetime'] == datetime.datetime(2009, 1, 1, 12,
                0, 0))

            self.failUnlessRaises(Exception, self.datetime_required.create, {})
            transaction.cursor.rollback()

            datetime6_id = self.datetime_required.create({
                'datetime': today,
                })
            self.assert_(datetime6_id)

            datetime7_id = self.datetime.create({
                'datetime': None,
                })
            self.assert_(datetime7_id)

            datetime8_id = self.datetime.create({
                'datetime': False,
                })
            self.assert_(datetime8_id)

            datetime9_id = self.datetime.create({
                'datetime': today.replace(microsecond=1),
                })
            self.assert_(datetime9_id)
            datetime9 = self.datetime.read(datetime9_id, ['datetime'])
            self.assert_(datetime9['datetime'] == today)

            transaction.cursor.rollback()

    def test0100one2one(self):
        '''
        Test One2One.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1_id = self.one2one_target.create({
                'name': 'target1',
                })
            one2one1_id = self.one2one.create({
                'name': 'origin1',
                'one2one': target1_id,
                })
            self.assert_(one2one1_id)

            one2one1 = self.one2one.read(one2one1_id, ['one2one',
                'one2one.name'])
            self.assert_(one2one1['one2one'] == target1_id)
            self.assert_(one2one1['one2one.name'] == 'target1')

            one2one_ids = self.one2one.search([
                ('one2one', '=', 'target1'),
                ])
            self.assert_(one2one_ids == [one2one1_id])

            one2one_ids = self.one2one.search([
                ('one2one', '!=', 'target1'),
                ])
            self.assert_(one2one_ids == [])

            one2one_ids = self.one2one.search([
                ('one2one', 'in', [target1_id]),
                ])
            self.assert_(one2one_ids == [one2one1_id])

            one2one_ids = self.one2one.search([
                ('one2one', 'in', [0]),
                ])
            self.assert_(one2one_ids == [])

            one2one_ids = self.one2one.search([
                ('one2one', 'not in', [target1_id]),
                ])
            self.assert_(one2one_ids == [])

            one2one_ids = self.one2one.search([
                ('one2one', 'not in', [0]),
                ])
            self.assert_(one2one_ids == [one2one1_id])

            one2one_ids = self.one2one.search([
                ('one2one.name', '=', 'target1'),
                ])
            self.assert_(one2one_ids == [one2one1_id])

            one2one_ids = self.one2one.search([
                ('one2one.name', '!=', 'target1'),
                ])
            self.assert_(one2one_ids == [])

            one2one = self.one2one.browse(one2one1_id)
            self.assert_(one2one.one2one.name == 'target1')

            one2one2_id = self.one2one.create({
                'name': 'origin2',
                })
            self.assert_(one2one2_id)

            one2one2 = self.one2one.read(one2one2_id, ['one2one'])
            self.assert_(one2one2['one2one'] == False)

            one2one_ids = self.one2one.search([
                ('one2one', '=', False),
                ])
            self.assert_(one2one_ids == [one2one2_id])

            target2_id = self.one2one_target.create({
                'name': 'target2',
                })
            self.one2one.write(one2one2_id, {
                'one2one': target2_id,
                })
            target2_id = self.one2one_target.search([
                ('name', '=', 'target2'),
                ])[0]
            one2one2 = self.one2one.read(one2one2_id, ['one2one'])
            self.assert_(one2one2['one2one'] == target2_id)

            self.one2one.write(one2one2_id, {
                'one2one': False,
                })
            one2one2 = self.one2one.read(one2one2_id, ['one2one'])
            self.assert_(one2one2['one2one'] == False)

            one2one2 = self.one2one.browse(one2one2_id)
            self.assert_(not one2one2.one2one)

            self.failUnlessRaises(Exception, self.one2one.create, {
                'name': 'one2one3',
                'one2one': target1_id,
                })
            transaction.cursor.rollback()

            self.failUnlessRaises(Exception, self.one2one.write, one2one2_id, {
                'one2one': target1_id,
                })
            transaction.cursor.rollback()

            self.failUnlessRaises(Exception, self.one2one_required.create, {
                'name': 'one2one3',
                })
            transaction.cursor.rollback()

            target3_id = self.one2one_target.create({
                'name': 'target3_id',
                })

            one2one3_id = self.one2one_required.create({
                'name': 'one2one3',
                'one2one': target3_id,
                })
            self.assert_(one2one3_id)

            transaction.cursor.rollback()

    def test0110property(self):
        '''
        Test Property with supported field types.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            # Test Char
            prop_id_a = self.property_.create({'char': 'Test'})
            self.assert_(prop_id_a)

            prop_id_b = self.property_.create({})
            self.assert_(prop_id_b)

            prop_id_c = self.property_.create({'char': 'FooBar'})
            self.assert_(prop_id_c)

            prop_a = self.property_.read(prop_id_a, ['char'])
            self.assert_(prop_a['char'] == 'Test')

            prop_ids = self.property_.search([('char', '=', 'Test')])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([('char', '=', False)])
            self.assert_(prop_ids == [prop_id_b])

            prop_ids = self.property_.search([('char', '!=', False)])
            self.assert_(prop_ids == [prop_id_a, prop_id_c])

            prop_ids = self.property_.search([('char', 'like', 'Tes%')])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([('char', 'like', '%Bar')])
            self.assert_(prop_ids == [prop_id_c])

            prop_ids = self.property_.search([('char', 'not like', 'Tes%')])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            prop_ids = self.property_.search([('char', 'ilike', 'tes%')])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([('char', 'ilike', '%bar')])
            self.assert_(prop_ids == [prop_id_c])

            prop_ids = self.property_.search([('char', 'not ilike', 'tes%')])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            prop_ids = self.property_.search([('char', 'in', ['Test'])])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([
                    ('char', 'in', ['Test', 'FooBar'])])
            self.assert_(prop_ids == [prop_id_a, prop_id_c])

            prop_ids = self.property_.search([
                    ('char', 'not in', ['Test', 'FooBar'])])
            self.assert_(prop_ids == [prop_id_b])

            model_field_obj = POOL.get('ir.model.field')
            property_obj = POOL.get('ir.property')

            # Test default value
            property_field_id, = model_field_obj.search([
                        ('model.model', '=', 'test.property'),
                        ('name', '=', 'char'),
                    ], limit=1)
            property_obj.create({
                        'field': property_field_id,
                        'value': ',DEFAULT_VALUE',
                    })

            prop_id_d = self.property_.create({})
            self.assert_(prop_id_d)

            prop = self.property_.read(prop_id_d, ['char'])
            self.assert_(prop['char'] == 'DEFAULT_VALUE')

            prop_ids = self.property_.search([('char', '!=', False)])
            self.assert_(prop_ids == [prop_id_a, prop_id_c, prop_id_d])

            self.property_.write(prop_id_a, {'char': False})
            prop_a = self.property_.read(prop_id_a, ['char'])
            self.assert_(prop_a['char'] == False)

            self.property_.write(prop_id_b, {'char': 'Test'})
            prop_b = self.property_.read(prop_id_b, ['char'])
            self.assert_(prop_b['char'] == 'Test')

            transaction.cursor.rollback()


            # Test Many2One
            char_id_a = self.char.create({'char': 'Test'})
            self.assert_(char_id_a)

            char_id_b = self.char.create({'char': 'FooBar'})
            self.assert_(char_id_b)

            prop_id_a = self.property_.create({'many2one': char_id_a})
            self.assert_(prop_id_a)

            prop_id_b = self.property_.create({'many2one': char_id_b})
            self.assert_(prop_id_b)

            prop_id_c = self.property_.create({})
            self.assert_(prop_id_c)

            prop_ids = self.property_.search([('many2one', '=', char_id_a)])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([('many2one', '!=', False)])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([('many2one', '=', False)])
            self.assert_(prop_ids == [prop_id_c])

            prop_a = self.property_.read(prop_id_a, ['many2one'])
            self.assert_(prop_a['many2one'] == char_id_a)

            prop_ids = self.property_.search([
                    ('many2one', 'in', [char_id_a, char_id_b])])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([
                    ('many2one', 'not in', [char_id_a, char_id_b])])
            self.assert_(prop_ids == [prop_id_c])

            self.property_.write(prop_id_b, {'many2one': char_id_a})
            prop_b = self.property_.read(prop_id_b, ['many2one'])
            self.assert_(prop_b['many2one'] == char_id_a)

            transaction.cursor.rollback()


            # Test Numeric
            prop_id_a = self.property_.create({'numeric': Decimal('1.1')})
            self.assert_(prop_id_a)

            prop_id_b = self.property_.create({'numeric': Decimal('2.6')})
            self.assert_(prop_id_b)

            prop_id_c = self.property_.create({})
            self.assert_(prop_id_c)

            prop_ids = self.property_.search([('numeric', '!=', False)])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([('numeric', '=', False)])
            self.assert_(prop_ids == [prop_id_c])

            prop_ids = self.property_.search([('numeric', '=', Decimal('1.1'))])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([
                    ('numeric', '!=', Decimal('1.1'))])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            prop_ids = self.property_.search([('numeric', '<', Decimal('2.6'))])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([
                    ('numeric', '<=', Decimal('2.6'))])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([('numeric', '>', Decimal('1.1'))])
            self.assert_(prop_ids == [prop_id_b])

            prop_ids = self.property_.search([
                    ('numeric', '>=', Decimal('1.1'))])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([
                    ('numeric', 'in', [Decimal('1.1')])])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([
                    ('numeric', 'in', [Decimal('1.1'), Decimal('2.6')])])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([
                    ('numeric', 'not in', [Decimal('1.1')])])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            prop_ids = self.property_.search([
                    ('numeric', 'not in', [Decimal('1.1'), Decimal('2.6')])])
            self.assert_(prop_ids == [prop_id_c])

            # Test default value
            property_field_id, = model_field_obj.search([
                        ('model.model', '=', 'test.property'),
                        ('name', '=', 'numeric'),
                    ], limit=1)
            property_obj.create({
                        'field': property_field_id,
                        'value': ',3.7',
                    })

            prop_id_d = self.property_.create({})
            self.assert_(prop_id_d)

            prop_d = self.property_.read(prop_id_d, ['numeric'])
            self.assert_(prop_d['numeric'] == Decimal('3.7'))

            self.property_.write(prop_id_a, {'numeric': False})
            prop_a = self.property_.read(prop_id_a, ['numeric'])
            self.assert_(prop_a['numeric'] == False)

            self.property_.write(prop_id_b, {'numeric': Decimal('3.11')})
            prop_b = self.property_.read(prop_id_b, ['numeric'])
            self.assert_(prop_b['numeric'] == Decimal('3.11'))

            transaction.cursor.rollback()


            # Test Selection
            prop_id_a = self.property_.create({'selection': 'option_a'})
            self.assert_(prop_id_a)

            prop_id_b = self.property_.create({'selection': 'option_b'})
            self.assert_(prop_id_b)

            prop_id_c = self.property_.create({})
            self.assert_(prop_id_c)

            prop_ids = self.property_.search([('selection', '=', 'option_a')])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([('selection', '!=', False)])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([('selection', '=', False)])
            self.assert_(prop_ids == [prop_id_c])

            prop_ids = self.property_.search([('selection', '!=', 'option_a')])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            prop_ids = self.property_.search([
                    ('selection', 'in', ['option_a'])])
            self.assert_(prop_ids == [prop_id_a])

            prop_ids = self.property_.search([
                    ('selection', 'in', ['option_a', 'option_b'])])
            self.assert_(prop_ids == [prop_id_a, prop_id_b])

            prop_ids = self.property_.search([
                    ('selection', 'not in', ['option_a'])])
            self.assert_(prop_ids == [prop_id_b, prop_id_c])

            # Test default value
            property_field_id, = model_field_obj.search([
                        ('model.model', '=', 'test.property'),
                        ('name', '=', 'selection'),
                    ], limit=1)
            property_obj.create({
                        'field': property_field_id,
                        'value': ',option_a',
                    })

            prop_id_d = self.property_.create({})
            self.assert_(prop_id_d)

            prop_d = self.property_.read(prop_id_d, ['selection'])
            self.assert_(prop_d['selection'] == 'option_a')

            self.property_.write(prop_id_a, {'selection': False})
            prop_a = self.property_.read(prop_id_a, ['selection'])
            self.assert_(prop_a['selection'] == False)

            self.property_.write(prop_id_c, {'selection': 'option_b'})
            prop_c = self.property_.read(prop_id_c, ['selection'])
            self.assert_(prop_c['selection'] == 'option_b')

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldsTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
