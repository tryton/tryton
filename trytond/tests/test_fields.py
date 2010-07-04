#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import datetime
from decimal import Decimal
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module


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

    def test0010boolean(self):
        '''
        Test Boolean.
        '''
        cursor = DB.cursor()

        boolean1_id = self.boolean.create(cursor, USER, {
            'boolean': True,
            }, CONTEXT)
        self.assert_(boolean1_id)

        boolean1 = self.boolean.read(cursor, USER, boolean1_id, ['boolean'],
                CONTEXT)
        self.assert_(boolean1['boolean'] == True)

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', '=', True),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', '!=', True),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'in', [True]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'not in', [True]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean2_id = self.boolean.create(cursor, USER, {
            'boolean': False,
            }, CONTEXT)
        self.assert_(boolean2_id)

        boolean2 = self.boolean.read(cursor, USER, boolean2_id, ['boolean'],
                CONTEXT)
        self.assert_(boolean2['boolean'] == False)

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean2_id])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'in', [True, False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id, boolean2_id])

        boolean_ids = self.boolean.search(cursor, USER, [
            ('boolean', 'not in', [True, False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean3_id = self.boolean.create(cursor, USER, {}, CONTEXT)
        self.assert_(boolean3_id)

        boolean3 = self.boolean.read(cursor, USER, boolean3_id, ['boolean'],
                CONTEXT)
        self.assert_(boolean3['boolean'] == False)

        boolean4_id = self.boolean_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(boolean4_id)

        boolean4 = self.boolean_default.read(cursor, USER, boolean4_id,
                ['boolean'], CONTEXT)
        self.assert_(boolean4['boolean'] == True)

        self.boolean.write(cursor, USER, boolean1_id, {
            'boolean': False,
            }, CONTEXT)
        boolean1 = self.boolean.read(cursor, USER, boolean1_id, ['boolean'],
                CONTEXT)
        self.assert_(boolean1['boolean'] == False)

        self.boolean.write(cursor, USER, boolean2_id, {
            'boolean': True,
            }, CONTEXT)
        boolean2 = self.boolean.read(cursor, USER, boolean2_id, ['boolean'],
                CONTEXT)
        self.assert_(boolean2['boolean'] == True)

        cursor.rollback()
        cursor.close()

    def test0020integer(self):
        '''
        Test Integer.
        '''
        cursor = DB.cursor()

        integer1_id = self.integer.create(cursor, USER, {
            'integer': 1,
            }, CONTEXT)
        self.assert_(integer1_id)

        integer1 = self.integer.read(cursor, USER, integer1_id, ['integer'],
                CONTEXT)
        self.assert_(integer1['integer'] == 1)

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '!=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '!=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'in', [1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'not in', [1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'not in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '<=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '>=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer2_id = self.integer.create(cursor, USER, {
            'integer': 0,
            }, CONTEXT)
        self.assert_(integer2_id)

        integer2 = self.integer.read(cursor, USER, integer2_id, ['integer'],
                CONTEXT)
        self.assert_(integer2['integer'] == 0)

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer2_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'in', [0, 1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id, integer2_id])

        integer_ids = self.integer.search(cursor, USER, [
            ('integer', 'not in', [0, 1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer3_id = self.integer.create(cursor, USER, {}, CONTEXT)
        self.assert_(integer3_id)

        integer3 = self.integer.read(cursor, USER, integer3_id, ['integer'],
                CONTEXT)
        self.assert_(integer3['integer'] == 0)

        integer4_id = self.integer_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(integer4_id)

        integer4 = self.integer_default.read(cursor, USER, integer4_id,
                ['integer'], CONTEXT)
        self.assert_(integer4['integer'] == 5)

        self.integer.write(cursor, USER, integer1_id, {
            'integer': 0,
            }, CONTEXT)
        integer1 = self.integer.read(cursor, USER, integer1_id, ['integer'],
                CONTEXT)
        self.assert_(integer1['integer'] == 0)

        self.integer.write(cursor, USER, integer2_id, {
            'integer': 1,
            }, CONTEXT)
        integer2 = self.integer.read(cursor, USER, integer2_id, ['integer'],
                CONTEXT)
        self.assert_(integer2['integer'] == 1)

        self.failUnlessRaises(Exception, self.integer.create, cursor, USER, {
            'integer': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.integer.write, cursor, USER,
                integer1_id, {
                    'integer': 'test',
                    }, CONTEXT)

        integer5_id = self.integer_required.create(cursor, USER, {}, CONTEXT)
        self.assert_(integer5_id)

        integer5 = self.integer_required.read(cursor, USER, integer5_id,
                ['integer'], CONTEXT)
        self.assert_(integer5['integer'] == 0)

        cursor.rollback()
        cursor.close()

    def test0030float(self):
        '''
        Test Float.
        '''
        cursor = DB.cursor()

        float1_id = self.float.create(cursor, USER, {
            'float': 1.1,
            }, CONTEXT)
        self.assert_(float1_id)

        float1 = self.float.read(cursor, USER, float1_id, ['float'], CONTEXT)
        self.assert_(float1['float'] == 1.1)

        float_ids = self.float.search(cursor, USER, [
            ('float', '=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '!=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '!=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'in', [1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'not in', [1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'not in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '<=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', '>=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float2_id = self.float.create(cursor, USER, {
            'float': 0,
            }, CONTEXT)
        self.assert_(float2_id)

        float2 = self.float.read(cursor, USER, float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 0)

        float_ids = self.float.search(cursor, USER, [
            ('float', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float2_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'in', [0, 1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id, float2_id])

        float_ids = self.float.search(cursor, USER, [
            ('float', 'not in', [0, 1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float3_id = self.float.create(cursor, USER, {}, CONTEXT)
        self.assert_(float3_id)

        float3 = self.float.read(cursor, USER, float3_id, ['float'], CONTEXT)
        self.assert_(float3['float'] == 0)

        float4_id = self.float_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(float4_id)

        float4 = self.float_default.read(cursor, USER, float4_id, ['float'],
                CONTEXT)
        self.assert_(float4['float'] == 5.5)

        self.float.write(cursor, USER, float1_id, {
            'float': 0,
            }, CONTEXT)
        float1 = self.float.read(cursor, USER, float1_id, ['float'] , CONTEXT)
        self.assert_(float1['float'] == 0)

        self.float.write(cursor, USER, float2_id, {
            'float': 1.1,
            }, CONTEXT)
        float2 = self.float.read(cursor, USER, float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 1.1)

        self.failUnlessRaises(Exception, self.float.create, cursor, USER, {
            'float': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.float.write, float1_id, cursor,
                USER, {
                    'float': 'test',
                    }, CONTEXT)

        float5_id = self.float_required.create(cursor, USER, {}, CONTEXT)
        self.assert_(float5_id)

        float5 = self.float_required.read(cursor, USER, float5_id, ['float'],
                CONTEXT)
        self.assert_(float5['float'] == 0)

        float6_id = self.float_digits.create(cursor, USER, {
            'digits': 1,
            'float': 1.1,
            }, CONTEXT)
        self.assert_(float6_id)

        self.failUnlessRaises(Exception, self.float_digits.create, cursor,
                USER, {
                    'digits': 1,
                    'float': 1.11,
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.float_digits.write, cursor,
                USER, float6_id, {
                    'float': 1.11,
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.float_digits.write, cursor,
                USER, float6_id, {
                    'digits': 0,
                    }, CONTEXT)

        float7_id = self.float.create(cursor, USER, {
            'float': 0.123456789012345,
            }, CONTEXT)

        float7 = self.float.read(cursor, USER, float7_id, ['float'], CONTEXT)
        self.assert_(float7['float'] == 0.123456789012345)

        cursor.rollback()
        cursor.close()

    def test0040numeric(self):
        '''
        Test Numeric.
        '''
        cursor = DB.cursor()

        numeric1_id = self.numeric.create(cursor, USER, {
            'numeric': Decimal('1.1'),
            }, CONTEXT)
        self.assert_(numeric1_id)

        numeric1 = self.numeric.read(cursor, USER, numeric1_id, ['numeric'],
                CONTEXT)
        self.assert_(numeric1['numeric'] == Decimal('1.1'))

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '!=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '!=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'in', [Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'in', [Decimal('0')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'not in', [Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'not in', [Decimal('0')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<=', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<=', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '<=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>=', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>=', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '>=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric2_id = self.numeric.create(cursor, USER, {
            'numeric': Decimal('0'),
            }, CONTEXT)
        self.assert_(numeric2_id)

        numeric2 = self.numeric.read(cursor, USER, numeric2_id, ['numeric'],
                CONTEXT)
        self.assert_(numeric2['numeric'] == Decimal('0'))

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', '=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric2_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'in', [Decimal('0'), Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id, numeric2_id])

        numeric_ids = self.numeric.search(cursor, USER, [
            ('numeric', 'not in', [Decimal('0'), Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric3_id = self.numeric.create(cursor, USER, {}, CONTEXT)
        self.assert_(numeric3_id)

        numeric3 = self.numeric.read(cursor, USER, numeric3_id, ['numeric'],
                CONTEXT)
        self.assert_(numeric3['numeric'] == Decimal('0'))

        numeric4_id = self.numeric_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(numeric4_id)

        numeric4 = self.numeric_default.read(cursor, USER, numeric4_id,
                ['numeric'], CONTEXT)
        self.assert_(numeric4['numeric'] == Decimal('5.5'))

        self.numeric.write(cursor, USER, numeric1_id, {
            'numeric': Decimal('0'),
            }, CONTEXT)
        numeric1 = self.numeric.read(cursor, USER, numeric1_id, ['numeric'] ,
                CONTEXT)
        self.assert_(numeric1['numeric'] == Decimal('0'))

        self.numeric.write(cursor, USER, numeric2_id, {
            'numeric': Decimal('1.1'),
            }, CONTEXT)
        numeric2 = self.numeric.read(cursor, USER, numeric2_id, ['numeric'],
                CONTEXT)
        self.assert_(numeric2['numeric'] == Decimal('1.1'))

        self.failUnlessRaises(Exception, self.numeric.create, cursor, USER, {
            'numeric': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.numeric.write, numeric1_id,
                cursor, USER, {
                    'numeric': 'test',
                    }, CONTEXT)

        numeric5_id = self.numeric_required.create(cursor, USER, {}, CONTEXT)
        self.assert_(numeric5_id)

        numeric5 = self.numeric_required.read(cursor, USER, numeric5_id,
                ['numeric'], CONTEXT)
        self.assert_(numeric5['numeric'] == Decimal('0'))

        numeric6_id = self.numeric_digits.create(cursor, USER, {
            'digits': 1,
            'numeric': Decimal('1.1'),
            }, CONTEXT)
        self.assert_(numeric6_id)

        self.failUnlessRaises(Exception, self.numeric_digits.create, cursor,
                USER, {
                    'digits': 1,
                    'numeric': Decimal('1.11'),
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.numeric_digits.write, cursor,
                USER, numeric6_id, {
                    'numeric': Decimal('1.11'),
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.numeric_digits.write, cursor,
                USER, numeric6_id, {
                    'digits': 0,
                    }, CONTEXT)

        numeric7_id = self.numeric.create(cursor, USER, {
            'numeric': Decimal('0.1234567890123456789'),
            }, CONTEXT)

        numeric7 = self.numeric.read(cursor, USER, numeric7_id, ['numeric'],
                CONTEXT)
        self.assert_(numeric7['numeric'] ==
                Decimal('0.1234567890123456789'))

        cursor.rollback()
        cursor.close()

    def test0050char(self):
        '''
        Test Char.
        '''
        cursor = DB.cursor()

        for char in (self.char, self.char_translate):
            char1_id = char.create(cursor, USER, {
                'char': 'Test',
                }, CONTEXT)
            self.assert_(char1_id)

            char1 = char.read(cursor, USER, char1_id, ['char'], CONTEXT)
            self.assert_(char1['char'] == 'Test')

            char_ids = char.search(cursor, USER, [
                ('char', '=', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', '=', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', '=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', '!=', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', '!=', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', '!=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'in', ['Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'in', ['Foo']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'in', [False]),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'in', []),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not in', ['Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not in', ['Foo']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not in', [False]),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not in', []),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'like', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'like', 'T%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'like', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'like', 'F%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'ilike', 'test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'ilike', 't%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'ilike', 'foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'ilike', 'f%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not like', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not like', 'T%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not like', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not like', 'F%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not ilike', 'test'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not ilike', 't%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

            char_ids = char.search(cursor, USER, [
                ('char', 'not ilike', 'foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not ilike', 'f%'),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id])

            char2_id = char.create(cursor, USER, {
                'char': False,
                }, CONTEXT)
            self.assert_(char2_id)

            char2 = char.read(cursor, USER, char2_id, ['char'], CONTEXT)
            self.assert_(char2['char'] == None)

            char_ids = char.search(cursor, USER, [
                ('char', '=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char2_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'in', [False, 'Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [char1_id, char2_id])

            char_ids = char.search(cursor, USER, [
                ('char', 'not in', [False, 'Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(char_ids == [])

        char3_id = self.char.create(cursor, USER, {}, CONTEXT)
        self.assert_(char3_id)

        char3 = self.char.read(cursor, USER, char3_id, ['char'], CONTEXT)
        self.assert_(char3['char'] == None)

        char4_id = self.char_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(char4_id)

        char4 = self.char_default.read(cursor, USER, char4_id, ['char'],
                CONTEXT)
        self.assert_(char4['char'] == 'Test')

        self.char.write(cursor, USER, char1_id, {
            'char': False,
            }, CONTEXT)
        char1 = self.char.read(cursor, USER, char1_id, ['char'], CONTEXT)
        self.assert_(char1['char'] == None)

        self.char.write(cursor, USER, char2_id, {
            'char': 'Test',
            }, CONTEXT)
        char2 = self.char.read(cursor, USER, char2_id, ['char'], CONTEXT)
        self.assert_(char2['char'] == 'Test')

        self.failUnlessRaises(Exception, self.char_required.create, cursor,
                USER, {}, CONTEXT)
        cursor.rollback()

        char5_id = self.char_required.create(cursor, USER, {
            'char': 'Test',
            }, CONTEXT)
        self.assert_(char5_id)

        char6_id = self.char_size.create(cursor, USER, {
            'char': 'Test',
            }, CONTEXT)
        self.assert_(char6_id)

        self.failUnlessRaises(Exception, self.char_size.create, cursor, USER, {
            'char': 'foobar',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.char_size.write, cursor, USER,
                char6_id, {
                    'char': 'foobar',
                    }, CONTEXT)
        cursor.rollback()

        char7_id = self.char.create(cursor, USER, {
            'char': u'é',
            }, CONTEXT)
        self.assert_(char7_id)

        char7 = self.char.read(cursor, USER, char7_id, ['char'], CONTEXT)
        self.assert_(char7['char'] == u'é')

        char_ids = self.char.search(cursor, USER, [
            ('char', '=', u'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char7_id])

        self.char.write(cursor, USER, char7_id, {
            'char': 'é',
            }, CONTEXT)
        char7 = self.char.read(cursor, USER, char7_id, ['char'], CONTEXT)
        self.assert_(char7['char'] == u'é')

        char_ids = self.char.search(cursor, USER, [
            ('char', '=', 'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char7_id])

        cursor.rollback()
        cursor.close()

    def test0060text(self):
        '''
        Test Text.
        '''
        cursor = DB.cursor()

        for text in (self.text, self.text_translate):
            text1_id = text.create(cursor, USER, {
                'text': 'Test',
                }, CONTEXT)
            self.assert_(text1_id)

            text1 = text.read(cursor, USER, text1_id, ['text'], CONTEXT)
            self.assert_(text1['text'] == 'Test')

            text_ids = text.search(cursor, USER, [
                ('text', '=', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', '=', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', '=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', '!=', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', '!=', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', '!=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'in', ['Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'in', ['Foo']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'in', [False]),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'in', []),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not in', ['Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not in', ['Foo']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not in', [False]),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not in', []),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'like', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'like', 'T%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'like', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'like', 'F%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'ilike', 'test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'ilike', 't%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'ilike', 'foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'ilike', 'f%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not like', 'Test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not like', 'T%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not like', 'Foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not like', 'F%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not ilike', 'test'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not ilike', 't%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

            text_ids = text.search(cursor, USER, [
                ('text', 'not ilike', 'foo'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not ilike', 'f%'),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id])

            text2_id = text.create(cursor, USER, {
                'text': False,
                }, CONTEXT)
            self.assert_(text2_id)

            text2 = text.read(cursor, USER, text2_id, ['text'], CONTEXT)
            self.assert_(text2['text'] == None)

            text_ids = text.search(cursor, USER, [
                ('text', '=', False),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text2_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'in', [False, 'Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [text1_id, text2_id])

            text_ids = text.search(cursor, USER, [
                ('text', 'not in', [False, 'Test']),
                ], 0, None, None, CONTEXT)
            self.assert_(text_ids == [])

        text3_id = self.text.create(cursor, USER, {}, CONTEXT)
        self.assert_(text3_id)

        text3 = self.text.read(cursor, USER, text3_id, ['text'], CONTEXT)
        self.assert_(text3['text'] == None)

        text4_id = self.text_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(text4_id)

        text4 = self.text_default.read(cursor, USER, text4_id, ['text'],
                CONTEXT)
        self.assert_(text4['text'] == 'Test')

        self.text.write(cursor, USER, text1_id, {
            'text': False,
            }, CONTEXT)
        text1 = self.text.read(cursor, USER, text1_id, ['text'], CONTEXT)
        self.assert_(text1['text'] == None)

        self.text.write(cursor, USER, text2_id, {
            'text': 'Test',
            }, CONTEXT)
        text2 = self.text.read(cursor, USER, text2_id, ['text'], CONTEXT)
        self.assert_(text2['text'] == 'Test')

        self.failUnlessRaises(Exception, self.text_required.create, cursor,
                USER, {}, CONTEXT)
        cursor.rollback()

        text5_id = self.text_required.create(cursor, USER, {
            'text': 'Test',
            }, CONTEXT)
        self.assert_(text5_id)

        text6_id = self.text_size.create(cursor, USER, {
            'text': 'Test',
            }, CONTEXT)
        self.assert_(text6_id)

        self.failUnlessRaises(Exception, self.text_size.create, cursor, USER, {
            'text': 'foobar',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.text_size.write, cursor, USER,
                text6_id, {
                    'text': 'foobar',
                    }, CONTEXT)

        text7_id = self.text.create(cursor, USER, {
            'text': 'Foo\nBar',
            }, CONTEXT)
        self.assert_(text7_id)

        text8_id = self.text.create(cursor, USER, {
            'text': u'é',
            }, CONTEXT)
        self.assert_(text8_id)

        text8 = self.text.read(cursor, USER, text8_id, ['text'], CONTEXT)
        self.assert_(text8['text'] == u'é')

        text_ids = self.text.search(cursor, USER, [
            ('text', '=', u'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text8_id])

        self.text.write(cursor, USER, text8_id, {
            'text': 'é',
            }, CONTEXT)
        text8 = self.text.read(cursor, USER, text8_id, ['text'], CONTEXT)
        self.assert_(text8['text'] == u'é')

        text_ids = self.text.search(cursor, USER, [
            ('text', '=', 'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text8_id])

        cursor.rollback()
        cursor.close()

    def test0070sha(self):
        '''
        Test Sha.
        '''
        cursor = DB.cursor()

        sha1_id = self.sha.create(cursor, USER, {
            'sha': 'Test',
            }, CONTEXT)
        self.assert_(sha1_id)

        sha1 = self.sha.read(cursor, USER, sha1_id, ['sha'], CONTEXT)
        self.assert_(sha1['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '!=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '!=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'like', '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'like', '640a%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'ilike', '640AB2BAE07BEDC4C163F679A746F7AB7FB5D1FA'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'ilike', '640A%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not like', '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not like', '640a%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not ilike', '640AB2BAE07BEDC4C163F679A746F7AB7FB5D1FA'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not ilike', '640A%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha2_id = self.sha.create(cursor, USER, {
            'sha': False,
            }, CONTEXT)
        self.assert_(sha2_id)

        sha2 = self.sha.read(cursor, USER, sha2_id, ['sha'], CONTEXT)
        self.assert_(sha2['sha'] == None)

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha2_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id, sha2_id])

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', 'not in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha3_id = self.sha.create(cursor, USER, {}, CONTEXT)
        self.assert_(sha3_id)

        sha3 = self.sha.read(cursor, USER, sha3_id, ['sha'], CONTEXT)
        self.assert_(sha3['sha'] == None)

        sha4_id = self.sha_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(sha4_id)

        sha4 = self.sha_default.read(cursor, USER, sha4_id, ['sha'], CONTEXT)
        self.assert_(sha4['sha'] == 'ba79baeb9f10896a46ae74715271b7f586e74640')

        self.sha.write(cursor, USER, sha1_id, {
            'sha': False,
            }, CONTEXT)
        sha1 = self.sha.read(cursor, USER, sha1_id, ['sha'], CONTEXT)
        self.assert_(sha1['sha'] == None)

        self.sha.write(cursor, USER, sha2_id, {
            'sha': 'Test',
            }, CONTEXT)
        sha2 = self.sha.read(cursor, USER, sha2_id, ['sha'], CONTEXT)
        self.assert_(sha2['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

        self.failUnlessRaises(Exception, self.sha_required.create, cursor,
                USER, {}, CONTEXT)
        cursor.rollback()

        sha5_id = self.sha_required.create(cursor, USER, {
            'sha': 'Test',
            }, CONTEXT)
        self.assert_(sha5_id)

        sha6_id = self.sha.create(cursor, USER, {
            'sha': u'é',
            }, CONTEXT)
        self.assert_(sha6_id)

        sha6 = self.sha.read(cursor, USER, sha6_id, ['sha'], CONTEXT)
        self.assert_(sha6['sha'] ==
                u'bf15be717ac1b080b4f1c456692825891ff5073d')

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', u'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha6_id])

        self.sha.write(cursor, USER, sha6_id, {
            'sha': 'é',
            }, CONTEXT)
        sha6 = self.sha.read(cursor, USER, sha6_id, ['sha'], CONTEXT)
        self.assert_(sha6['sha'] ==
                u'bf15be717ac1b080b4f1c456692825891ff5073d')

        sha_ids = self.sha.search(cursor, USER, [
            ('sha', '=', 'é'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha6_id])

        cursor.rollback()
        cursor.close()

    def test0080date(self):
        '''
        Test Date.
        '''
        cursor = DB.cursor()

        today = datetime.date(2009, 1, 1)
        tomorrow = today + datetime.timedelta(1)
        yesterday = today - datetime.timedelta(1)
        default_date = datetime.date(2000, 1, 1)

        date1_id = self.date.create(cursor, USER, {
            'date': today,
            }, CONTEXT)
        self.assert_(date1_id)

        date1 = self.date.read(cursor, USER, date1_id, ['date'], CONTEXT)
        self.assert_(date1['date'] == today)

        date_ids = self.date.search(cursor, USER, [
            ('date', '=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '!=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '!=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'in', [today]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'in', [tomorrow]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'not in', [today]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'not in', [tomorrow]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '<=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', '>=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id])

        date2_id = self.date.create(cursor, USER, {
            'date': yesterday,
            }, CONTEXT)
        self.assert_(date2_id)

        date2 = self.date.read(cursor, USER, date2_id, ['date'], CONTEXT)
        self.assert_(date2['date'] == yesterday)

        date_ids = self.date.search(cursor, USER, [
            ('date', '=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date2_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'in', [yesterday, today]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [date1_id, date2_id])

        date_ids = self.date.search(cursor, USER, [
            ('date', 'not in', [yesterday, today]),
            ], 0, None, None, CONTEXT)
        self.assert_(date_ids == [])

        date3_id = self.date.create(cursor, USER, {}, CONTEXT)
        self.assert_(date3_id)

        date3 = self.date.read(cursor, USER, date3_id, ['date'], CONTEXT)
        self.assert_(date3['date'] == None)

        date4_id = self.date_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(date4_id)

        date4 = self.date_default.read(cursor, USER, date4_id, ['date'],
                CONTEXT)
        self.assert_(date4['date'] == default_date)

        self.date.write(cursor, USER, date1_id, {
            'date': yesterday,
            }, CONTEXT)
        date1 = self.date.read(cursor, USER, date1_id, ['date'], CONTEXT)
        self.assert_(date1['date'] == yesterday)

        self.date.write(cursor, USER, date2_id, {
            'date': today,
            }, CONTEXT)
        date2 = self.date.read(cursor, USER, date2_id, ['date'], CONTEXT)
        self.assert_(date2['date'] == today)

        self.failUnlessRaises(Exception, self.date.create, cursor, USER, {
            'date': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.write, cursor, USER,
                date1_id, {
                    'date': 'test',
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.create, cursor, USER, {
            'date': 1,
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.write, cursor, USER,
                date1_id, {
                    'date': 1,
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.create, cursor, USER, {
                'date': datetime.datetime.now(),
                }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.write, cursor, USER,
                date1_id, {
                    'date': datetime.datetime.now(),
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.create, cursor, USER, {
                'date': '2009-13-01',
                }, CONTEXT)

        self.failUnlessRaises(Exception, self.date.write, cursor, USER,
                date1_id, {
                    'date': '2009-02-29',
                    }, CONTEXT)

        date5_id = self.date.create(cursor, USER, {
            'date': '2009-01-01',
            }, CONTEXT)
        self.assert_(date5_id)
        date5 = self.date.read(cursor, USER, date5_id, ['date'], CONTEXT)
        self.assert_(date5['date'] == datetime.date(2009, 1, 1))

        self.failUnlessRaises(Exception, self.date_required.create, cursor,
                USER, {}, CONTEXT)
        cursor.rollback()

        date6_id = self.date_required.create(cursor, USER, {
            'date': today,
            }, CONTEXT)
        self.assert_(date6_id)

        date7_id = self.date.create(cursor, USER, {
            'date': None,
            }, CONTEXT)
        self.assert_(date7_id)

        date8_id = self.date.create(cursor, USER, {
            'date': False,
            }, CONTEXT)
        self.assert_(date8_id)

        cursor.rollback()
        cursor.close()

    def test0090datetime(self):
        '''
        Test DateTime.
        '''
        cursor = DB.cursor()

        today = datetime.datetime(2009, 1, 1, 12, 0, 0)
        tomorrow = today + datetime.timedelta(1)
        yesterday = today - datetime.timedelta(1)
        default_datetime = datetime.datetime(2000, 1, 1, 12, 0, 0)

        datetime1_id = self.datetime.create(cursor, USER, {
            'datetime': today,
            }, CONTEXT)
        self.assert_(datetime1_id)

        datetime1 = self.datetime.read(cursor, USER, datetime1_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime1['datetime'] == today)

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '!=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '!=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'in', [today]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'in', [tomorrow]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'not in', [today]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'not in', [tomorrow]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '<=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>=', tomorrow),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '>=', today),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id])

        datetime2_id = self.datetime.create(cursor, USER, {
            'datetime': yesterday,
            }, CONTEXT)
        self.assert_(datetime2_id)

        datetime2 = self.datetime.read(cursor, USER, datetime2_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime2['datetime'] == yesterday)

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', '=', yesterday),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime2_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'in', [yesterday, today]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [datetime1_id, datetime2_id])

        datetime_ids = self.datetime.search(cursor, USER, [
            ('datetime', 'not in', [yesterday, today]),
            ], 0, None, None, CONTEXT)
        self.assert_(datetime_ids == [])

        datetime3_id = self.datetime.create(cursor, USER, {}, CONTEXT)
        self.assert_(datetime3_id)

        datetime3 = self.datetime.read(cursor, USER, datetime3_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime3['datetime'] == None)

        datetime4_id = self.datetime_default.create(cursor, USER, {}, CONTEXT)
        self.assert_(datetime4_id)

        datetime4 = self.datetime_default.read(cursor, USER, datetime4_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime4['datetime'] == default_datetime)

        self.datetime.write(cursor, USER, datetime1_id, {
            'datetime': yesterday,
            }, CONTEXT)
        datetime1 = self.datetime.read(cursor, USER, datetime1_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime1['datetime'] == yesterday)

        self.datetime.write(cursor, USER, datetime2_id, {
            'datetime': today,
            }, CONTEXT)
        datetime2 = self.datetime.read(cursor, USER, datetime2_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime2['datetime'] == today)

        self.failUnlessRaises(Exception, self.datetime.create, cursor, USER, {
            'datetime': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.write, cursor, USER,
                datetime1_id, {
                    'datetime': 'test',
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.create, cursor, USER, {
            'datetime': 1,
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.write, cursor, USER,
                datetime1_id, {
                    'datetime': 1,
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.create, cursor, USER, {
            'datetime': datetime.date.today(),
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.write, cursor, USER,
                datetime1_id, {
                    'datetime': datetime.date.today(),
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.create, cursor, USER, {
            'datetime': '2009-13-01 12:30:00',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.write, cursor, USER,
                datetime1_id, {
                    'datetime': '2009-02-29 12:30:00',
                    }, CONTEXT)

        self.failUnlessRaises(Exception, self.datetime.write, cursor, USER,
                datetime1_id, {
                    'datetime': '2009-01-01 25:00:00',
                    }, CONTEXT)

        datetime5_id = self.datetime.create(cursor, USER, {
            'datetime': '2009-01-01 12:00:00',
            }, CONTEXT)
        self.assert_(datetime5_id)
        datetime5 = self.datetime.read(cursor, USER, datetime5_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime5['datetime'] == datetime.datetime(2009, 1, 1, 12,
            0, 0))

        self.failUnlessRaises(Exception, self.datetime_required.create, cursor,
                USER, {}, CONTEXT)
        cursor.rollback()

        datetime6_id = self.datetime_required.create(cursor, USER, {
            'datetime': today,
            }, CONTEXT)
        self.assert_(datetime6_id)

        datetime7_id = self.datetime.create(cursor, USER, {
            'datetime': None,
            }, CONTEXT)
        self.assert_(datetime7_id)

        datetime8_id = self.datetime.create(cursor, USER, {
            'datetime': False,
            }, CONTEXT)
        self.assert_(datetime8_id)

        datetime9_id = self.datetime.create(cursor, USER, {
            'datetime': today.replace(microsecond=1),
            }, CONTEXT)
        self.assert_(datetime9_id)
        datetime9 = self.datetime.read(cursor, USER, datetime9_id,
                ['datetime'], CONTEXT)
        self.assert_(datetime9['datetime'] == today)

        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldsTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
