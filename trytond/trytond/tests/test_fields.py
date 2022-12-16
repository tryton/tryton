#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
try:
    import cdecimal
    if 'decimal' not in sys.modules:
        sys.modules['decimal'] = cdecimal
except ImportError:
    import decimal
    sys.modules['cdecimal'] = decimal
import unittest
import datetime
from decimal import Decimal
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


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
        self.datetime_format = POOL.get('test.datetime_format')

        self.time = POOL.get('test.time')
        self.time_default = POOL.get('test.time_default')
        self.time_required = POOL.get('test.time_required')
        self.time_format = POOL.get('test.time_format')

        self.one2one = POOL.get('test.one2one')
        self.one2one_target = POOL.get('test.one2one.target')
        self.one2one_required = POOL.get('test.one2one_required')

        self.one2many = POOL.get('test.one2many')
        self.one2many_target = POOL.get('test.one2many.target')
        self.one2many_required = POOL.get('test.one2many_required')
        self.one2many_reference = POOL.get('test.one2many_reference')
        self.one2many_reference_target = POOL.get(
            'test.one2many_reference.target')
        self.one2many_size = POOL.get('test.one2many_size')
        self.one2many_size_pyson = POOL.get('test.one2many_size_pyson')

        self.many2many = POOL.get('test.many2many')
        self.many2many_target = POOL.get('test.many2many.target')
        self.many2many_required = POOL.get('test.many2many_required')
        self.many2many_reference = POOL.get('test.many2many_reference')
        self.many2many_reference_target = POOL.get(
            'test.many2many_reference.target')
        self.many2many_size = POOL.get('test.many2many_size')
        self.many2many_size_target = POOL.get('test.many2many_size.target')

        self.reference = POOL.get('test.reference')
        self.reference_target = POOL.get('test.reference.target')
        self.reference_required = POOL.get('test.reference_required')

        self.property_ = POOL.get('test.property')
        self.ir_property = POOL.get('ir.property')
        self.model_field = POOL.get('ir.model.field')

        self.selection = POOL.get('test.selection')
        self.selection_required = POOL.get('test.selection_required')

        self.dict_ = POOL.get('test.dict')
        self.dict_default = POOL.get('test.dict_default')
        self.dict_required = POOL.get('test.dict_required')

    def test0010boolean(self):
        '''
        Test Boolean.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            boolean1, = self.boolean.create([{
                        'boolean': True,
                        }])
            self.assert_(boolean1)
            self.assertEqual(boolean1.boolean, True)

            booleans = self.boolean.search([
                    ('boolean', '=', True),
                    ])
            self.assertEqual(booleans, [boolean1])

            booleans = self.boolean.search([
                    ('boolean', '!=', True),
                    ])
            self.assertEqual(booleans, [])

            booleans = self.boolean.search([
                    ('boolean', 'in', [True]),
                    ])
            self.assertEqual(booleans, [boolean1])

            booleans = self.boolean.search([
                    ('boolean', 'in', [False]),
                    ])
            self.assertEqual(booleans, [])

            booleans = self.boolean.search([
                    ('boolean', 'not in', [True]),
                    ])
            self.assertEqual(booleans, [])

            booleans = self.boolean.search([
                    ('boolean', 'not in', [False]),
                    ])
            self.assertEqual(booleans, [boolean1])

            boolean2, = self.boolean.create([{
                        'boolean': False,
                        }])
            self.assert_(boolean2)
            self.assertEqual(boolean2.boolean, False)

            booleans = self.boolean.search([
                    ('boolean', '=', False),
                    ])
            self.assertEqual(booleans, [boolean2])

            booleans = self.boolean.search([
                    ('boolean', 'in', [True, False]),
                    ])
            self.assertEqual(booleans, [boolean1, boolean2])

            booleans = self.boolean.search([
                    ('boolean', 'not in', [True, False]),
                    ])
            self.assertEqual(booleans, [])

            boolean3, = self.boolean.create([{}])
            self.assert_(boolean3)
            self.assertEqual(boolean3.boolean, False)

            # Test search with NULL value
            boolean4, = self.boolean.create([{
                        'boolean': None,
                        }])
            self.assert_(boolean4)

            booleans = self.boolean.search([
                    ('boolean', '=', False),
                    ])
            self.assertEqual(booleans,
                [boolean2, boolean3, boolean4])

            booleans = self.boolean.search([
                    ('boolean', '!=', False),
                    ])
            self.assertEqual(booleans, [boolean1])

            boolean4, = self.boolean_default.create([{}])
            self.assert_(boolean4)
            self.assertTrue(boolean4.boolean)

            self.boolean.write([boolean1], {
                    'boolean': False,
                    })
            self.assertEqual(boolean1.boolean, False)

            self.boolean.write([boolean2], {
                    'boolean': True,
                    })
            self.assertEqual(boolean2.boolean, True)

            transaction.cursor.rollback()

    def test0020integer(self):
        '''
        Test Integer.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            integer1, = self.integer.create([{
                        'integer': 1,
                        }])
            self.assert_(integer1)
            self.assertEqual(integer1.integer, 1)

            integers = self.integer.search([
                    ('integer', '=', 1),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '=', 0),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '!=', 1),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '!=', 0),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', 'in', [1]),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', 'in', [0]),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', 'in', []),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', 'not in', [1]),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', 'not in', [0]),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', 'not in', []),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '<', 5),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '<', -5),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '<', 1),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '<=', 5),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '<=', -5),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '<=', 1),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '>', 5),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '>', -5),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '>', 1),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '>=', 5),
                    ])
            self.assertEqual(integers, [])

            integers = self.integer.search([
                    ('integer', '>=', -5),
                    ])
            self.assertEqual(integers, [integer1])

            integers = self.integer.search([
                    ('integer', '>=', 1),
                    ])
            self.assertEqual(integers, [integer1])

            integer2, = self.integer.create([{
                        'integer': 0,
                        }])
            self.assert_(integer2)
            self.assertEqual(integer2.integer, 0)

            integers = self.integer.search([
                    ('integer', '=', 0),
                    ])
            self.assertEqual(integers, [integer2])

            integers = self.integer.search([
                    ('integer', 'in', [0, 1]),
                    ])
            self.assertEqual(integers, [integer1, integer2])

            integers = self.integer.search([
                    ('integer', 'not in', [0, 1]),
                    ])
            self.assertEqual(integers, [])

            integer3, = self.integer.create([{}])
            self.assert_(integer3)
            self.assertEqual(integer3.integer, None)

            integer4, = self.integer_default.create([{}])
            self.assert_(integer4)
            self.assertEqual(integer4.integer, 5)

            self.integer.write([integer1], {
                    'integer': 0,
                    })
            self.assertEqual(integer1.integer, 0)

            self.integer.write([integer2], {
                    'integer': 1,
                    })
            self.assertEqual(integer2.integer, 1)

            self.assertRaises(Exception, self.integer.create, [{
                        'integer': 'test',
                        }])

            self.assertRaises(Exception, self.integer.write, [integer1], {
                    'integer': 'test',
                    })

            # We should catch UserError but mysql does not raise an
            # IntegrityError but an OperationalError
            self.assertRaises(Exception, self.integer_required.create, [{}])
            transaction.cursor.rollback()

            integer5, = self.integer_required.create([{
                        'integer': 0,
                        }])
            self.assert_(integer5)
            self.assertEqual(integer5.integer, 0)

            transaction.cursor.rollback()

    def test0030float(self):
        '''
        Test Float.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            float1, = self.float.create([{
                        'float': 1.1,
                        }])
            self.assert_(float1)
            self.assertEqual(float1.float, 1.1)

            floats = self.float.search([
                    ('float', '=', 1.1),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '=', 0),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '!=', 1.1),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '!=', 0),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', 'in', [1.1]),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', 'in', [0]),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', 'in', []),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', 'not in', [1.1]),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', 'not in', [0]),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', 'not in', []),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '<', 5),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '<', -5),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '<', 1.1),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '<=', 5),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '<=', -5),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '<=', 1.1),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '>', 5),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '>', -5),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '>', 1.1),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '>=', 5),
                    ])
            self.assertEqual(floats, [])

            floats = self.float.search([
                    ('float', '>=', -5),
                    ])
            self.assertEqual(floats, [float1])

            floats = self.float.search([
                    ('float', '>=', 1.1),
                    ])
            self.assertEqual(floats, [float1])

            float2, = self.float.create([{
                        'float': 0,
                        }])
            self.assert_(float2)
            self.assertEqual(float2.float, 0)

            floats = self.float.search([
                    ('float', '=', 0),
                    ])
            self.assertEqual(floats, [float2])

            floats = self.float.search([
                    ('float', 'in', [0, 1.1]),
                    ])
            self.assertEqual(floats, [float1, float2])

            floats = self.float.search([
                    ('float', 'not in', [0, 1.1]),
                    ])
            self.assertEqual(floats, [])

            float3, = self.float.create([{}])
            self.assert_(float3)
            self.assertEqual(float3.float, None)

            float4, = self.float_default.create([{}])
            self.assert_(float4)
            self.assertEqual(float4.float, 5.5)

            self.float.write([float1], {
                    'float': 0,
                    })
            self.assertEqual(float1.float, 0)

            self.float.write([float2], {
                    'float': 1.1,
                    })
            self.assertEqual(float2.float, 1.1)

            self.assertRaises(Exception, self.float.create, [{
                        'float': 'test',
                        }])

            self.assertRaises(Exception, self.float.write, [float1], {
                    'float': 'test',
                    })

            self.assertRaises(Exception, self.float_required.create, [{}])
            transaction.cursor.rollback()

            float5, = self.float_required.create([{
                        'float': 0.0,
                        }])
            self.assertEqual(float5.float, 0.0)

            float6, = self.float_digits.create([{
                        'digits': 1,
                        'float': 1.1,
                        }])
            self.assert_(float6)

            self.assertRaises(Exception, self.float_digits.create, [{
                        'digits': 1,
                        'float': 1.11,
                        }])

            self.assertRaises(Exception, self.float_digits.write,
                [float6], {
                    'float': 1.11,
                    })

            self.assertRaises(Exception, self.float_digits.write,
                [float6], {
                    'digits': 0,
                    })

            float7, = self.float.create([{
                        'float': 0.123456789012345,
                        }])
            self.assertEqual(float7.float, 0.123456789012345)

            transaction.cursor.rollback()

    def test0040numeric(self):
        '''
        Test Numeric.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            numeric1, = self.numeric.create([{
                        'numeric': Decimal('1.1'),
                        }])
            self.assert_(numeric1)
            self.assertEqual(numeric1.numeric, Decimal('1.1'))

            numerics = self.numeric.search([
                    ('numeric', '=', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '=', Decimal('0')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '!=', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '!=', Decimal('0')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', 'in', [Decimal('1.1')]),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', 'in', [Decimal('0')]),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', 'in', []),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', 'not in', [Decimal('1.1')]),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', 'not in', [Decimal('0')]),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', 'not in', []),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '<', Decimal('5')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '<', Decimal('-5')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '<', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '<=', Decimal('5')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '<=', Decimal('-5')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '<=', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '>', Decimal('5')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '>', Decimal('-5')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '>', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '>=', Decimal('5')),
                    ])
            self.assertEqual(numerics, [])

            numerics = self.numeric.search([
                    ('numeric', '>=', Decimal('-5')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numerics = self.numeric.search([
                    ('numeric', '>=', Decimal('1.1')),
                    ])
            self.assertEqual(numerics, [numeric1])

            numeric2, = self.numeric.create([{
                        'numeric': Decimal('0'),
                        }])
            self.assert_(numeric2)
            self.assertEqual(numeric2.numeric, Decimal('0'))

            numerics = self.numeric.search([
                    ('numeric', '=', Decimal('0')),
                    ])
            self.assertEqual(numerics, [numeric2])

            numerics = self.numeric.search([
                    ('numeric', 'in', [Decimal('0'), Decimal('1.1')]),
                    ])
            self.assertEqual(numerics, [numeric1, numeric2])

            numerics = self.numeric.search([
                    ('numeric', 'not in', [Decimal('0'), Decimal('1.1')]),
                    ])
            self.assertEqual(numerics, [])

            numeric3, = self.numeric.create([{}])
            self.assert_(numeric3)
            self.assertEqual(numeric3.numeric, None)

            numeric4, = self.numeric_default.create([{}])
            self.assert_(numeric4)
            self.assertEqual(numeric4.numeric, Decimal('5.5'))

            self.numeric.write([numeric1], {
                    'numeric': Decimal('0'),
                    })
            self.assertEqual(numeric1.numeric, Decimal('0'))

            self.numeric.write([numeric2], {
                    'numeric': Decimal('1.1'),
                    })
            self.assertEqual(numeric2.numeric, Decimal('1.1'))

            self.assertRaises(Exception, self.numeric.create, [{
                        'numeric': 'test',
                        }])

            self.assertRaises(Exception, self.numeric.write, [numeric1], {
                    'numeric': 'test',
                    })

            self.assertRaises(Exception, self.numeric_required.create, [{}])
            transaction.cursor.rollback()

            numeric5, = self.numeric_required.create([{
                    'numeric': Decimal(0),
                    }])
            self.assertEqual(numeric5.numeric, 0)

            numeric6, = self.numeric_digits.create([{
                        'digits': 1,
                        'numeric': Decimal('1.1'),
                        }])
            self.assert_(numeric6)

            self.assertRaises(Exception, self.numeric_digits.create, [{
                        'digits': 1,
                        'numeric': Decimal('1.11'),
                        }])

            self.assertRaises(Exception, self.numeric_digits.write,
                [numeric6], {
                    'numeric': Decimal('1.11'),
                    })

            self.assertRaises(Exception, self.numeric_digits.write,
                [numeric6], {
                    'numeric': Decimal('0.10000000000000001'),
                    })

            self.assertRaises(Exception, self.numeric_digits.write,
                [numeric6], {
                    'digits': 0,
                    })

            numeric7, = self.numeric.create([{
                        'numeric': Decimal('0.1234567890123456789'),
                        }])
            self.assertEqual(numeric7.numeric,
                Decimal('0.1234567890123456789'))

            transaction.cursor.rollback()

    def test0050char(self):
        '''
        Test Char.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for char in (self.char_translate, self.char):
                char1, = char.create([{
                            'char': 'Test',
                            }])
                self.assert_(char1)
                self.assertEqual(char1.char, 'Test')

                chars = char.search([
                        ('char', '=', 'Test'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', '=', 'Foo'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', '=', None),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', '!=', 'Test'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', '!=', 'Foo'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', '!=', None),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'in', ['Test']),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'in', ['Foo']),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'in', [None]),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'in', []),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not in', ['Test']),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not in', ['Foo']),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'not in', [None]),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'not in', []),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'like', 'Test'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'like', 'T%'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'like', 'Foo'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'like', 'F%'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'ilike', 'test'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'ilike', 't%'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'ilike', 'foo'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'ilike', 'f%'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not like', 'Test'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not like', 'T%'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not like', 'Foo'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'not like', 'F%'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'not ilike', 'test'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not ilike', 't%'),
                        ])
                self.assertEqual(chars, [])

                chars = char.search([
                        ('char', 'not ilike', 'foo'),
                        ])
                self.assertEqual(chars, [char1])

                chars = char.search([
                        ('char', 'not ilike', 'f%'),
                        ])
                self.assertEqual(chars, [char1])

                char2, = char.create([{
                            'char': None,
                            }])
                self.assert_(char2)
                self.assertEqual(char2.char, None)

                chars = char.search([
                        ('char', '=', None),
                        ])
                self.assertEqual(chars, [char2])

                chars = char.search([
                        ('char', 'in', [None, 'Test']),
                        ])
                self.assertEqual(chars, [char1, char2])

                chars = char.search([
                        ('char', 'not in', [None, 'Test']),
                        ])
                self.assertEqual(chars, [])

            char3, = self.char.create([{}])
            self.assert_(char3)
            self.assertEqual(char3.char, None)

            char4, = self.char_default.create([{}])
            self.assert_(char4)
            self.assertEqual(char4.char, 'Test')

            self.char.write([char1], {
                    'char': None,
                    })
            self.assertEqual(char1.char, None)

            self.char.write([char2], {
                    'char': 'Test',
                    })
            self.assertEqual(char2.char, 'Test')

            self.assertRaises(Exception, self.char_required.create, [{}])
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.char_required.create, [{
                    'char': '',
                    }])
            transaction.cursor.rollback()

            char5, = self.char_required.create([{
                        'char': 'Test',
                        }])
            self.assert_(char5)

            char6, = self.char_size.create([{
                        'char': 'Test',
                        }])
            self.assert_(char6)

            self.assertRaises(Exception, self.char_size.create, [{
                    'char': 'foobar',
                    }])

            self.assertRaises(Exception, self.char_size.write, [char6], {
                    'char': 'foobar',
                    })
            transaction.cursor.rollback()

            char7, = self.char.create([{
                        'char': u'é',
                        }])
            self.assert_(char7)
            self.assertEqual(char7.char, u'é')

            chars = self.char.search([
                    ('char', '=', u'é'),
                    ])
            self.assertEqual(chars, [char7])

            self.char.write([char7], {
                    'char': 'é',
                    })
            self.assertEqual(char7.char, u'é')

            chars = self.char.search([
                    ('char', '=', 'é'),
                    ])
            self.assertEqual(chars, [char7])

            transaction.cursor.rollback()

    def test0060text(self):
        '''
        Test Text.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for text in (self.text_translate, self.text):
                text1, = text.create([{
                            'text': 'Test',
                            }])
                self.assert_(text1)
                self.assertEqual(text1.text, 'Test')

                texts = text.search([
                        ('text', '=', 'Test'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', '=', 'Foo'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', '=', None),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', '!=', 'Test'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', '!=', 'Foo'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', '!=', None),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'in', ['Test']),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'in', ['Foo']),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'in', [None]),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'in', []),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not in', ['Test']),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not in', ['Foo']),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'not in', [None]),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'not in', []),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'like', 'Test'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'like', 'T%'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'like', 'Foo'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'like', 'F%'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'ilike', 'test'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'ilike', 't%'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'ilike', 'foo'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'ilike', 'f%'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not like', 'Test'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not like', 'T%'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not like', 'Foo'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'not like', 'F%'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'not ilike', 'test'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not ilike', 't%'),
                        ])
                self.assertEqual(texts, [])

                texts = text.search([
                        ('text', 'not ilike', 'foo'),
                        ])
                self.assertEqual(texts, [text1])

                texts = text.search([
                        ('text', 'not ilike', 'f%'),
                        ])
                self.assertEqual(texts, [text1])

                text2, = text.create([{
                            'text': None,
                            }])
                self.assert_(text2)
                self.assertEqual(text2.text, None)

                texts = text.search([
                        ('text', '=', None),
                        ])
                self.assertEqual(texts, [text2])

                texts = text.search([
                        ('text', 'in', [None, 'Test']),
                        ])
                self.assertEqual(texts, [text1, text2])

                texts = text.search([
                        ('text', 'not in', [None, 'Test']),
                        ])
                self.assertEqual(texts, [])

            text3, = self.text.create([{}])
            self.assert_(text3)
            self.assertEqual(text3.text, None)

            text4, = self.text_default.create([{}])
            self.assert_(text4)
            self.assertEqual(text4.text, 'Test')

            self.text.write([text1], {
                    'text': None,
                    })
            self.assertEqual(text1.text, None)

            self.text.write([text2], {
                    'text': 'Test',
                    })
            self.assertEqual(text2.text, 'Test')

            self.assertRaises(Exception, self.text_required.create, [{}])
            transaction.cursor.rollback()

            text5, = self.text_required.create([{
                        'text': 'Test',
                        }])
            self.assert_(text5)

            text6, = self.text_size.create([{
                        'text': 'Test',
                        }])
            self.assert_(text6)

            self.assertRaises(Exception, self.text_size.create, [{
                        'text': 'foobar',
                        }])

            self.assertRaises(Exception, self.text_size.write, [text6], {
                    'text': 'foobar',
                    })

            text7, = self.text.create([{
                        'text': 'Foo\nBar',
                        }])
            self.assert_(text7)

            text8, = self.text.create([{
                        'text': u'é',
                        }])
            self.assert_(text8)
            self.assertEqual(text8.text, u'é')

            texts = self.text.search([
                    ('text', '=', u'é'),
                    ])
            self.assertEqual(texts, [text8])

            self.text.write([text8], {
                    'text': 'é',
                    })
            self.assertEqual(text8.text, u'é')

            texts = self.text.search([
                    ('text', '=', 'é'),
                    ])
            self.assertEqual(texts, [text8])

            transaction.cursor.rollback()

    def test0070sha(self):
        '''
        Test Sha.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            sha1, = self.sha.create([{
                        'sha': 'Test',
                        }])
            self.assert_(sha1)
            self.assertEqual(sha1.sha,
                '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

            sha = self.sha.search([
                    ('sha', '=', 'Test'),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', '=', 'Foo'),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', '=', None),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', '!=', 'Test'),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', '!=', 'Foo'),
                    ])
            self.assert_(sha, [sha1])

            sha = self.sha.search([
                    ('sha', '!=', None),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'in', ['Test']),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'in', ['Foo']),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'in', [None]),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'in', []),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'not in', ['Test']),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'not in', ['Foo']),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'not in', [None]),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'not in', []),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'like', 'Test'),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'like', 'Foo'),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'ilike', 'Test'),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'ilike', 'foo'),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'not like', 'Test'),
                    ])
            self.assertEqual(sha, [])

            sha = self.sha.search([
                    ('sha', 'not like', 'Foo'),
                    ])
            self.assertEqual(sha, [sha1])

            sha = self.sha.search([
                    ('sha', 'not ilike', 'foo'),
                    ])
            self.assertEqual(sha, [sha1])

            sha2, = self.sha.create([{
                        'sha': None,
                        }])
            self.assert_(sha2)
            self.assertEqual(sha2.sha, None)

            sha = self.sha.search([
                    ('sha', '=', None),
                    ])
            self.assertEqual(sha, [sha2])

            sha = self.sha.search([
                    ('sha', 'in', [None, 'Test']),
                    ])
            self.assertEqual(sha, [sha1, sha2])

            sha = self.sha.search([
                    ('sha', 'not in', [None, 'Test']),
                    ])
            self.assertEqual(sha, [])

            sha3, = self.sha.create([{}])
            self.assert_(sha3)
            self.assertEqual(sha3.sha, None)

            sha4, = self.sha_default.create([{}])
            self.assert_(sha4)
            self.assertEqual(sha4.sha,
                'ba79baeb9f10896a46ae74715271b7f586e74640')

            self.sha.write([sha1], {
                    'sha': None,
                    })
            self.assertEqual(sha1.sha, None)

            self.sha.write([sha2], {
                    'sha': 'Test',
                    })
            self.assertEqual(sha2.sha,
                '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

            self.assertRaises(Exception, self.sha_required.create, [{}])
            transaction.cursor.rollback()

            sha5, = self.sha_required.create([{
                        'sha': 'Test',
                        }])
            self.assert_(sha5)

            sha6, = self.sha.create([{
                        'sha': u'é',
                        }])
            self.assert_(sha6)
            self.assertEqual(sha6.sha,
                u'bf15be717ac1b080b4f1c456692825891ff5073d')

            sha = self.sha.search([
                    ('sha', '=', u'é'),
                    ])
            self.assertEqual(sha, [sha6])

            self.sha.write([sha6], {
                    'sha': 'é',
                    })
            self.assertEqual(sha6.sha,
                u'bf15be717ac1b080b4f1c456692825891ff5073d')

            sha = self.sha.search([
                    ('sha', '=', 'é'),
                    ])
            self.assertEqual(sha, [sha6])

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

            date1, = self.date.create([{
                        'date': today,
                        }])
            self.assert_(date1)
            self.assertEqual(date1.date, today)

            dates = self.date.search([
                    ('date', '=', today),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '=', tomorrow),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '=', None),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '!=', today),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '!=', tomorrow),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '!=', None),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', 'in', [today]),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', 'in', [tomorrow]),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', 'in', [None]),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', 'in', []),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', 'not in', [today]),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', 'not in', [tomorrow]),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', 'not in', [None]),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', 'not in', []),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '<', tomorrow),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '<', yesterday),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '<', today),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '<=', today),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '<=', yesterday),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '<=', tomorrow),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '>', tomorrow),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '>', yesterday),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '>', today),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '>=', tomorrow),
                    ])
            self.assertEqual(dates, [])

            dates = self.date.search([
                    ('date', '>=', yesterday),
                    ])
            self.assertEqual(dates, [date1])

            dates = self.date.search([
                    ('date', '>=', today),
                    ])
            self.assertEqual(dates, [date1])

            date2, = self.date.create([{
                        'date': yesterday,
                        }])
            self.assert_(date2)
            self.assertEqual(date2.date, yesterday)

            dates = self.date.search([
                    ('date', '=', yesterday),
                    ])
            self.assertEqual(dates, [date2])

            dates = self.date.search([
                    ('date', 'in', [yesterday, today]),
                    ])
            self.assertEqual(dates, [date1, date2])

            dates = self.date.search([
                    ('date', 'not in', [yesterday, today]),
                    ])
            self.assertEqual(dates, [])

            date3, = self.date.create([{}])
            self.assert_(date3)
            self.assertEqual(date3.date, None)

            date4, = self.date_default.create([{}])
            self.assert_(date4)
            self.assertEqual(date4.date, default_date)

            self.date.write([date1], {
                    'date': yesterday,
                    })
            self.assertEqual(date1.date, yesterday)

            self.date.write([date2], {
                    'date': today,
                    })
            self.assertEqual(date2.date, today)

            self.assertRaises(Exception, self.date.create, [{
                        'date': 'test',
                        }])

            self.assertRaises(Exception, self.date.write, [date1], {
                    'date': 'test',
                    })

            self.assertRaises(Exception, self.date.create, [{
                        'date': 1,
                        }])

            self.assertRaises(Exception, self.date.write, [date1], {
                    'date': 1,
                    })

            self.assertRaises(Exception, self.date.create, [{
                        'date': datetime.datetime.now(),
                        }])

            self.assertRaises(Exception, self.date.write, [date1], {
                    'date': datetime.datetime.now(),
                    })

            self.assertRaises(Exception, self.date.create, [{
                        'date': '2009-13-01',
                        }])

            self.assertRaises(Exception, self.date.write, [date1], {
                    'date': '2009-02-29',
                    })

            date5, = self.date.create([{
                        'date': '2009-01-01',
                        }])
            self.assert_(date5)
            self.assertEqual(date5.date, datetime.date(2009, 1, 1))

            self.assertRaises(Exception, self.date_required.create, [{}])
            transaction.cursor.rollback()

            date6, = self.date_required.create([{
                        'date': today,
                        }])
            self.assert_(date6)

            date7, = self.date.create([{
                        'date': None,
                        }])
            self.assert_(date7)

            date8, = self.date.create([{
                        'date': None,
                        }])
            self.assert_(date8)

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

            datetime1, = self.datetime.create([{
                        'datetime': today,
                        }])
            self.assert_(datetime1)
            self.assertEqual(datetime1.datetime, today)

            datetimes = self.datetime.search([
                    ('datetime', '=', today),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '=', tomorrow),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '=', None),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '!=', today),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '!=', tomorrow),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '!=', None),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', 'in', [today]),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', 'in', [tomorrow]),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', 'in', [None]),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', 'in', []),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', 'not in', [today]),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', 'not in', [tomorrow]),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', 'not in', [None]),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', 'not in', []),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '<', tomorrow),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '<', yesterday),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '<', today),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '<=', today),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '<=', yesterday),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '<=', tomorrow),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '>', tomorrow),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '>', yesterday),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '>', today),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '>=', tomorrow),
                    ])
            self.assertEqual(datetimes, [])

            datetimes = self.datetime.search([
                    ('datetime', '>=', yesterday),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetimes = self.datetime.search([
                    ('datetime', '>=', today),
                    ])
            self.assertEqual(datetimes, [datetime1])

            datetime2, = self.datetime.create([{
                        'datetime': yesterday,
                        }])
            self.assert_(datetime2)
            self.assertEqual(datetime2.datetime, yesterday)

            datetimes = self.datetime.search([
                    ('datetime', '=', yesterday),
                    ])
            self.assertEqual(datetimes, [datetime2])

            datetimes = self.datetime.search([
                    ('datetime', 'in', [yesterday, today]),
                    ])
            self.assertEqual(datetimes, [datetime1, datetime2])

            datetimes = self.datetime.search([
                    ('datetime', 'not in', [yesterday, today]),
                    ])
            self.assertEqual(datetimes, [])

            datetime3, = self.datetime.create([{}])
            self.assert_(datetime3)
            self.assertEqual(datetime3.datetime, None)

            datetime4, = self.datetime_default.create([{}])
            self.assert_(datetime4)
            self.assertEqual(datetime4.datetime, default_datetime)

            self.datetime.write([datetime1], {
                    'datetime': yesterday,
                    })
            self.assertEqual(datetime1.datetime, yesterday)

            self.datetime.write([datetime2], {
                    'datetime': today,
                    })
            self.assertEqual(datetime2.datetime, today)

            self.assertRaises(Exception, self.datetime.create, [{
                        'datetime': 'test',
                        }])

            self.assertRaises(Exception, self.datetime.write, [datetime1],
                {
                    'datetime': 'test',
                    })

            self.assertRaises(Exception, self.datetime.create, [{
                        'datetime': 1,
                        }])

            self.assertRaises(Exception, self.datetime.write, [datetime1],
                {
                    'datetime': 1,
                    })

            self.assertRaises(Exception, self.datetime.create, [{
                        'datetime': datetime.date.today(),
                        }])

            self.assertRaises(Exception, self.datetime.write, [datetime1],
                {
                    'datetime': datetime.date.today(),
                    })

            self.assertRaises(Exception, self.datetime.create, [{
                        'datetime': '2009-13-01 12:30:00',
                        }])

            self.assertRaises(Exception, self.datetime.write, [datetime1],
                {
                    'datetime': '2009-02-29 12:30:00',
                    })

            self.assertRaises(Exception, self.datetime.write, [datetime1],
                {
                    'datetime': '2009-01-01 25:00:00',
                    })

            datetime5, = self.datetime.create([{
                    'datetime': '2009-01-01 12:00:00',
                    }])
            self.assert_(datetime5)
            self.assertEqual(datetime5.datetime,
                datetime.datetime(2009, 1, 1, 12, 0, 0))

            self.assertRaises(Exception, self.datetime_required.create, [{}])
            transaction.cursor.rollback()

            datetime6, = self.datetime_required.create([{
                        'datetime': today,
                        }])
            self.assert_(datetime6)

            datetime7, = self.datetime.create([{
                        'datetime': None,
                        }])
            self.assert_(datetime7)

            datetime8, = self.datetime.create([{
                        'datetime': None,
                        }])
            self.assert_(datetime8)

            datetime9, = self.datetime.create([{
                        'datetime': today.replace(microsecond=1),
                        }])
            self.assert_(datetime9)
            self.assertEqual(datetime9.datetime, today)

            # Test format
            self.assert_(self.datetime_format.create([{
                            'datetime': datetime.datetime(2009, 1, 1, 12, 30),
                            }]))
            self.assertRaises(Exception, self.datetime_format.create, [{
                        'datetime': datetime.datetime(2009, 1, 1, 12, 30, 25),
                        }])

            transaction.cursor.rollback()

    def test0100time(self):
        '''
        Test Time.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            pre_evening = datetime.time(16, 30)
            evening = datetime.time(18, 45, 3)
            night = datetime.time(20, 00)
            default_time = datetime.time(16, 30)

            time1, = self.time.create([{
                        'time': evening,
                        }])
            self.assert_(time1)
            self.assertEqual(time1.time, evening)

            times = self.time.search([
                    ('time', '=', evening),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '=', night),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '=', None),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '!=', evening),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '!=', night),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '!=', None),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', 'in', [evening]),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', 'in', [night]),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', 'in', [None]),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', 'in', []),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', 'not in', [evening]),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', 'not in', [night]),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', 'not in', [None]),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', 'not in', []),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '<', night),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '<', pre_evening),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '<', evening),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '<=', evening),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '<=', pre_evening),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '<=', night),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '>', night),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '>', pre_evening),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '>', evening),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '>=', night),
                    ])
            self.assertEqual(times, [])

            times = self.time.search([
                    ('time', '>=', pre_evening),
                    ])
            self.assertEqual(times, [time1])

            times = self.time.search([
                    ('time', '>=', evening),
                    ])
            self.assertEqual(times, [time1])

            time2, = self.time.create([{
                        'time': pre_evening,
                        }])
            self.assert_(time2)
            self.assertEqual(time2.time, pre_evening)

            times = self.time.search([
                    ('time', '=', pre_evening),
                    ])
            self.assertEqual(times, [time2])

            times = self.time.search([
                    ('time', 'in', [pre_evening, evening]),
                    ])
            self.assertEqual(times, [time1, time2])

            times = self.time.search([
                    ('time', 'not in', [pre_evening, evening]),
                    ])
            self.assertEqual(times, [])

            time3, = self.time.create([{}])
            self.assert_(time3)
            self.assertEqual(time3.time, None)

            time4, = self.time_default.create([{}])
            self.assert_(time4)
            self.assertEqual(time4.time, default_time)

            self.time.write([time1], {
                    'time': pre_evening,
                    })
            self.assertEqual(time1.time, pre_evening)

            self.time.write([time2], {
                    'time': evening,
                    })
            self.assertEqual(time2.time, evening)

            self.assertRaises(Exception, self.time.create, [{
                        'time': 'test',
                        }])

            self.assertRaises(Exception, self.time.write, [time1],
                {
                    'time': 'test',
                    })

            self.assertRaises(Exception, self.time.create, [{
                    'time': 1,
                    }])

            self.assertRaises(Exception, self.time.write, [time1],
                {
                    'time': 1,
                    })

            self.assertRaises(Exception, self.time.write, [time1],
                {
                    'time': '25:00:00',
                    })

            time5, = self.time.create([{
                        'time': '12:00:00',
                        }])
            self.assert_(time5)
            self.assertEqual(time5.time, datetime.time(12, 0))

            self.assertRaises(Exception, self.time_required.create, [{}])
            transaction.cursor.rollback()

            time6, = self.time_required.create([{
                        'time': evening,
                        }])
            self.assert_(time6)

            time7, = self.time.create([{
                        'time': None,
                        }])
            self.assert_(time7)

            time8, = self.time.create([{
                        'time': False,
                        }])
            self.assert_(time8)

            time9, = self.time.create([{
                        'time': evening.replace(microsecond=1),
                        }])
            self.assert_(time9)
            self.assertEqual(time9.time, evening)

            # Test format
            self.assert_(self.time_format.create([{
                        'time': datetime.time(12, 30),
                        }]))
            self.assertRaises(Exception, self.time_format.create, [{
                    'time': datetime.time(12, 30, 25),
                    }])

            transaction.cursor.rollback()

    def test0110one2one(self):
        '''
        Test One2One.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1, = self.one2one_target.create([{
                        'name': 'target1',
                        }])
            one2one1, = self.one2one.create([{
                        'name': 'origin1',
                        'one2one': target1.id,
                        }])
            self.assert_(one2one1)
            self.assertEqual(one2one1.one2one, target1)

            self.assertEqual(self.one2one.read([one2one1.id],
                    ['one2one.name'])[0]['one2one.name'], 'target1')

            one2ones = self.one2one.search([
                    ('one2one', '=', 'target1'),
                    ])
            self.assertEqual(one2ones, [one2one1])

            one2ones = self.one2one.search([
                    ('one2one', '!=', 'target1'),
                    ])
            self.assertEqual(one2ones, [])

            one2ones = self.one2one.search([
                    ('one2one', 'in', [target1.id]),
                    ])
            self.assertEqual(one2ones, [one2one1])

            one2ones = self.one2one.search([
                    ('one2one', 'in', [0]),
                    ])
            self.assertEqual(one2ones, [])

            one2ones = self.one2one.search([
                    ('one2one', 'not in', [target1.id]),
                    ])
            self.assertEqual(one2ones, [])

            one2ones = self.one2one.search([
                    ('one2one', 'not in', [0]),
                    ])
            self.assertEqual(one2ones, [one2one1])

            one2ones = self.one2one.search([
                    ('one2one.name', '=', 'target1'),
                    ])
            self.assertEqual(one2ones, [one2one1])

            one2ones = self.one2one.search([
                    ('one2one.name', '!=', 'target1'),
                    ])
            self.assertEqual(one2ones, [])

            one2one2, = self.one2one.create([{
                        'name': 'origin2',
                        }])
            self.assert_(one2one2)
            self.assertEqual(one2one2.one2one, None)

            one2ones = self.one2one.search([
                    ('one2one', '=', None),
                    ])
            self.assertEqual(one2ones, [one2one2])

            target2, = self.one2one_target.create([{
                        'name': 'target2',
                        }])
            self.one2one.write([one2one2], {
                    'one2one': target2.id,
                    })
            self.assertEqual(one2one2.one2one, target2)

            self.one2one.write([one2one2], {
                    'one2one': None,
                    })
            self.assertEqual(one2one2.one2one, None)

            self.assertRaises(Exception, self.one2one.create, [{
                        'name': 'one2one3',
                        'one2one': target1.id,
                        }])
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.one2one.write, [one2one2], {
                    'one2one': target1.id,
                    })
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.one2one_required.create, [{
                        'name': 'one2one3',
                        }])
            transaction.cursor.rollback()

            target3, = self.one2one_target.create([{
                        'name': 'target3',
                        }])

            one2one3, = self.one2one_required.create([{
                        'name': 'one2one3',
                        'one2one': target3.id,
                        }])
            self.assert_(one2one3)

            transaction.cursor.rollback()

    def test0120one2many(self):
        '''
        Test One2Many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for one2many, one2many_target in (
                    (self.one2many, self.one2many_target),
                    (self.one2many_reference, self.one2many_reference_target),
                    ):
                one2many1, = one2many.create([{
                            'name': 'origin1',
                            'targets': [
                                ('create', [{
                                            'name': 'target1',
                                            }]),
                                ],
                            }])
                self.assert_(one2many1)

                self.assertEqual(len(one2many1.targets), 1)
                target1, = one2many1.targets

                # Try with target1 stored in cache
                target1 = one2many_target(target1.id)
                target1.origin
                one2many1 = one2many(one2many1)
                self.assertEqual(one2many1.targets, (target1,))

                one2manys = one2many.search([
                        ('targets', '=', 'target1'),
                        ])
                self.assertEqual(one2manys, [one2many1])

                one2manys = one2many.search([
                        ('targets', '!=', 'target1'),
                        ])
                self.assertEqual(one2manys, [])

                one2manys = one2many.search([
                        ('targets', 'in', [target1.id]),
                        ])
                self.assertEqual(one2manys, [one2many1])

                one2manys = one2many.search([
                        ('targets', 'in', [0]),
                        ])
                self.assertEqual(one2manys, [])

                one2manys = one2many.search([
                        ('targets', 'not in', (target1.id,)),
                        ])
                self.assertEqual(one2manys, [])

                one2manys = one2many.search([
                        ('targets', 'not in', [0]),
                        ])
                self.assertEqual(one2manys, [one2many1])

                one2manys = one2many.search([
                        ('targets.name', '=', 'target1'),
                        ])
                self.assertEqual(one2manys, [one2many1])

                one2manys = one2many.search([
                        ('targets.name', '!=', 'target1'),
                        ])
                self.assertEqual(one2manys, [])

                one2many2, = one2many.create([{
                            'name': 'origin2',
                            }])
                self.assert_(one2many2)

                self.assertEqual(one2many2.targets, ())

                one2manys = one2many.search([
                        ('targets', '=', None),
                        ])
                self.assertEqual(one2manys, [one2many2])

                one2many.write([one2many1], {
                        'targets': [
                            ('write', [target1.id], {
                                    'name': 'target1bis',
                                    }),
                            ],
                        })
                self.assertEqual(target1.name, 'target1bis')

                target2, = one2many_target.create([{
                            'name': 'target2',
                            }])
                one2many.write([one2many1], {
                        'targets': [
                            ('add', [target2.id]),
                            ],
                        })
                self.assertEqual(one2many1.targets,
                    (target1, target2))

                one2many.write([one2many1], {
                        'targets': [
                            ('unlink', [target2.id]),
                            ],
                        })
                self.assertEqual(one2many1.targets, (target1,))
                target2, = one2many_target.search([
                        ('id', '=', target2.id),
                        ])
                self.assert_(target2)

                one2many.write([one2many1], {
                        'targets': [
                            ('unlink_all',),
                            ],
                        })
                self.assertEqual(one2many1.targets, ())
                targets = one2many_target.search([
                        ('id', 'in', [target1.id, target2.id]),
                        ])
                self.assertEqual(targets, [target1, target2])

                one2many.write([one2many1], {
                        'targets': [
                            ('set', [target1.id, target2.id]),
                            ],
                        })
                self.assertEqual(one2many1.targets,
                    (target1, target2))

                one2many.write([one2many1], {
                        'targets': [
                            ('delete', [target2.id]),
                            ],
                        })
                self.assertEqual(one2many1.targets, (target1,))
                targets = one2many_target.search([
                        ('id', '=', target2.id),
                        ])
                self.assertEqual(targets, [])

                one2many.write([one2many1], {
                        'targets': [
                            ('delete_all',),
                            ],
                        })
                self.assertEqual(one2many1.targets, ())
                targets = one2many_target.search([
                        ('id', '=', target1.id),
                        ])
                self.assertEqual(targets, [])

                transaction.cursor.rollback()

            self.assertRaises(Exception, self.one2many_required.create, [{
                        'name': 'origin3',
                        }])
            transaction.cursor.rollback()

            origin3_id, = self.one2many_required.create([{
                        'name': 'origin3',
                        'targets': [
                            ('create', [{
                                        'name': 'target3',
                                        }]),
                            ],
                        }])
            self.assert_(origin3_id)

            self.one2many_size.create([{
                        'targets': [('create', [{}])] * 3,
                        }])
            self.assertRaises(Exception, self.one2many_size.create, [{
                        'targets': [('create', [{}])] * 4,
                        }])
            self.one2many_size_pyson.create([{
                        'limit': 4,
                        'targets': [('create', [{}])] * 4,
                        }])
            self.assertRaises(Exception, self.one2many_size_pyson.create, [{
                        'limit': 2,
                        'targets': [('create', [{}])] * 4,
                        }])

            transaction.cursor.rollback()

    def test0130many2many(self):
        '''
        Test Many2Many.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            for many2many, many2many_target in (
                    (self.many2many, self.many2many_target),
                    (self.many2many_reference,
                        self.many2many_reference_target),
                    ):
                many2many1, = many2many.create([{
                            'name': 'origin1',
                            'targets': [
                                ('create', [{
                                            'name': 'target1',
                                            }]),
                                ],
                            }])
                self.assert_(many2many1)

                self.assertEqual(len(many2many1.targets), 1)
                target1, = many2many1.targets

                many2manys = many2many.search([
                        ('targets', '=', 'target1'),
                        ])
                self.assertEqual(many2manys, [many2many1])

                many2manys = many2many.search([
                        ('targets', '!=', 'target1'),
                        ])
                self.assertEqual(many2manys, [])

                many2manys = many2many.search([
                        ('targets', 'in', [target1.id]),
                        ])
                self.assertEqual(many2manys, [many2many1])

                many2manys = many2many.search([
                        ('targets', 'in', [0]),
                        ])
                self.assertEqual(many2manys, [])

                many2manys = many2many.search([
                        ('targets', 'not in', [target1.id]),
                        ])
                self.assertEqual(many2manys, [])

                many2manys = many2many.search([
                        ('targets', 'not in', [0]),
                        ])
                self.assertEqual(many2manys, [many2many1])

                many2manys = many2many.search([
                        ('targets.name', '=', 'target1'),
                        ])
                self.assertEqual(many2manys, [many2many1])

                many2manys = many2many.search([
                        ('targets.name', '!=', 'target1'),
                        ])
                self.assertEqual(many2manys, [])

                many2many2, = many2many.create([{
                            'name': 'origin2',
                            }])
                self.assert_(many2many2)

                self.assertEqual(many2many2.targets, ())

                many2manys = many2many.search([
                        ('targets', '=', None),
                        ])
                self.assertEqual(many2manys, [many2many2])

                many2many.write([many2many1], {
                        'targets': [
                            ('write', [target1.id], {
                                    'name': 'target1bis',
                                    }),
                            ],
                        })
                self.assertEqual(target1.name, 'target1bis')

                target2, = many2many_target.create([{
                            'name': 'target2',
                            }])
                many2many.write([many2many1], {
                        'targets': [
                            ('add', [target2.id]),
                            ],
                        })
                self.assertEqual(many2many1.targets,
                    (target1, target2))

                many2many.write([many2many1], {
                        'targets': [
                            ('unlink', [target2.id]),
                            ],
                        })
                self.assertEqual(many2many1.targets, (target1,))
                target2, = many2many_target.search([
                        ('id', '=', target2.id),
                        ])
                self.assert_(target2)

                many2many.write([many2many1], {
                        'targets': [
                            ('unlink_all',),
                            ],
                        })
                self.assertEqual(many2many1.targets, ())
                targets = many2many_target.search([
                        ('id', 'in', [target1.id, target2.id]),
                        ])
                self.assertEqual(targets, [target1, target2])

                many2many.write([many2many1], {
                        'targets': [
                            ('set', [target1.id, target2.id]),
                            ],
                        })
                self.assertEqual(many2many1.targets,
                    (target1, target2))

                many2many.write([many2many1], {
                        'targets': [
                            ('delete', [target2.id]),
                            ],
                        })
                self.assertEqual(many2many1.targets, (target1,))
                targets = many2many_target.search([
                        ('id', '=', target2.id),
                        ])
                self.assertEqual(targets, [])

                many2many.write([many2many1], {
                        'targets': [
                            ('delete_all',),
                            ],
                        })
                self.assertEqual(many2many1.targets, ())
                targets = many2many_target.search([
                        ('id', '=', target1.id),
                        ])
                self.assertEqual(targets, [])

                transaction.cursor.rollback()

            self.assertRaises(Exception, self.many2many_required.create, [{
                        'name': 'origin3',
                        }])
            transaction.cursor.rollback()

            origin3_id, = self.many2many_required.create([{
                        'name': 'origin3',
                        'targets': [
                            ('create', [{
                                        'name': 'target3',
                                        }]),
                            ],
                        }])
            self.assert_(origin3_id)

            size_targets = self.many2many_size_target.create([{
                        'name': str(i),
                        } for i in range(6)])

            self.many2many_size.create([{
                        'targets': [('set', size_targets[:5])],
                        }])
            self.assertRaises(Exception, self.many2many_size.create, [{
                        'targets': [('set', size_targets)],
                        }])

            transaction.cursor.rollback()

    def test0140reference(self):
        '''
        Test Reference.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            target1, = self.reference_target.create([{
                        'name': 'target1',
                        }])
            reference1, = self.reference.create([{
                        'name': 'reference1',
                        'reference': str(target1),
                        }])
            self.assert_(reference1)

            self.assertEqual(reference1.reference, target1)

            references = self.reference.search([
                    ('reference', '=', str(target1)),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference', '=', (target1.__name__, target1.id)),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference', '=', [target1.__name__, target1.id]),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference.name', '=', 'target1',
                        'test.reference.target'),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference', '!=', str(target1)),
                    ])
            self.assertEqual(references, [])

            references = self.reference.search([
                    ('reference', '!=', str(target1)),
                    ])
            self.assertEqual(references, [])

            references = self.reference.search([
                    ('reference', 'in', [str(target1)]),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference', 'in',
                        [('test.reference.target', target1.id)]),
                    ])
            self.assertEqual(references, [reference1])

            references = self.reference.search([
                    ('reference', 'in', [None]),
                    ])
            self.assertEqual(references, [])

            references = self.reference.search([
                    ('reference', 'not in', [str(target1)]),
                    ])
            self.assertEqual(references, [])

            references = self.reference.search([
                    ('reference', 'not in',
                        [('test.reference.target', target1.id)]),
                    ])
            self.assertEqual(references, [])

            references = self.reference.search([
                    ('reference', 'not in', [None]),
                    ])
            self.assertEqual(references, [reference1])

            reference2, = self.reference.create([{
                        'name': 'reference2',
                        }])
            self.assert_(reference2)

            self.assertEqual(reference2.reference, None)

            references = self.reference.search([
                    ('reference', '=', None),
                    ])
            self.assertEqual(references, [reference2])

            target2, = self.reference_target.create([{
                        'name': 'target2',
                        }])

            self.reference.write([reference2], {
                    'reference': str(target2),
                    })
            self.assertEqual(reference2.reference, target2)

            self.reference.write([reference2], {
                    'reference': None,
                    })
            self.assertEqual(reference2.reference, None)

            self.reference.write([reference2], {
                    'reference': ('test.reference.target', target2.id),
                    })
            self.assertEqual(reference2.reference, target2)

            reference3, = self.reference.create([{
                        'name': 'reference3',
                        'reference': ('test.reference.target', target1.id),
                        }])
            self.assert_(reference3)

            self.assertRaises(Exception, self.reference_required.create, [{
                        'name': 'reference4',
                        }])
            transaction.cursor.rollback()

            target4, = self.reference_target.create([{
                        'name': 'target4_id',
                        }])

            reference4, = self.reference_required.create([{
                        'name': 'reference4',
                        'reference': str(target4),
                        }])
            self.assert_(reference4)

            transaction.cursor.rollback()

    def test0150property(self):
        '''
        Test Property with supported field types.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:

            # Test Char
            prop_a, = self.property_.create([{'char': 'Test'}])
            self.assert_(prop_a)
            self.assertEqual(prop_a.char, 'Test')

            prop_b, = self.property_.create([{}])
            self.assert_(prop_b)
            self.assertEqual(prop_b.char, None)

            prop_c, = self.property_.create([{'char': 'FooBar'}])
            self.assert_(prop_c)
            self.assertEqual(prop_c.char, 'FooBar')

            props = self.property_.search([('char', '=', 'Test')])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([('char', '=', None)])
            self.assertEqual(props, [prop_b])

            props = self.property_.search([('char', '!=', None)])
            self.assertEqual(props, [prop_a, prop_c])

            props = self.property_.search([('char', 'like', 'Tes%')])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([('char', 'like', '%Bar')])
            self.assertEqual(props, [prop_c])

            props = self.property_.search([('char', 'not like', 'Tes%')])
            self.assertEqual(props, [prop_b, prop_c])

            props = self.property_.search([('char', 'ilike', 'tes%')])
            self.assert_(props, [prop_a])

            props = self.property_.search([('char', 'ilike', '%bar')])
            self.assertEqual(props, [prop_c])

            props = self.property_.search([('char', 'not ilike', 'tes%')])
            self.assertEqual(props, [prop_b, prop_c])

            props = self.property_.search([('char', 'in', ['Test'])])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([
                    ('char', 'in', ['Test', 'FooBar'])])
            self.assertEqual(props, [prop_a, prop_c])

            props = self.property_.search([
                    ('char', 'not in', ['Test', 'FooBar'])])
            self.assertEqual(props, [prop_b])

            # Test default value
            property_field, = self.model_field.search([
                    ('model.model', '=', 'test.property'),
                    ('name', '=', 'char'),
                    ], limit=1)
            self.ir_property.create([{
                        'field': property_field.id,
                        'value': ',DEFAULT_VALUE',
                        }])

            prop_d, = self.property_.create([{}])
            self.assert_(prop_d)
            self.assertEqual(prop_d.char, 'DEFAULT_VALUE')

            props = self.property_.search([('char', '!=', None)])
            self.assertEqual(props, [prop_a, prop_c, prop_d])

            self.property_.write([prop_a], {'char': None})
            self.assertEqual(prop_a.char, None)

            self.property_.write([prop_b], {'char': 'Test'})
            self.assertEqual(prop_b.char, 'Test')

            transaction.cursor.rollback()

            # Test Many2One
            char_a, = self.char.create([{'char': 'Test'}])
            self.assert_(char_a)

            char_b, = self.char.create([{'char': 'FooBar'}])
            self.assert_(char_b)

            prop_a, = self.property_.create([{'many2one': char_a.id}])
            self.assert_(prop_a)
            self.assertEqual(prop_a.many2one, char_a)

            prop_b, = self.property_.create([{'many2one': char_b.id}])
            self.assert_(prop_b)
            self.assertEqual(prop_b.many2one, char_b)

            prop_c, = self.property_.create([{}])
            self.assert_(prop_c)
            self.assertEqual(prop_c.many2one, None)

            props = self.property_.search([('many2one', '=', char_a.id)])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([('many2one', '!=', None)])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([('many2one', '=', None)])
            self.assertEqual(props, [prop_c])

            self.assertEqual(prop_a.many2one, char_a)

            props = self.property_.search([
                    ('many2one', 'in', [char_a.id, char_b.id])])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([
                    ('many2one', 'not in', [char_a.id, char_b.id])])
            self.assertEqual(props, [prop_c])

            self.property_.write([prop_b], {'many2one': char_a.id})
            self.assertEqual(prop_b.many2one, char_a)

            transaction.cursor.rollback()

            # Test Numeric
            prop_a, = self.property_.create([{'numeric': Decimal('1.1')}])
            self.assert_(prop_a)
            self.assertEqual(prop_a.numeric, Decimal('1.1'))

            prop_b, = self.property_.create([{'numeric': Decimal('2.6')}])
            self.assert_(prop_b)
            self.assertEqual(prop_b.numeric, Decimal('2.6'))

            prop_c, = self.property_.create([{}])
            self.assert_(prop_c)
            self.assertEqual(prop_c.numeric, None)

            props = self.property_.search([('numeric', '!=', None)])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([('numeric', '=', None)])
            self.assertEqual(props, [prop_c])

            props = self.property_.search([
                    ('numeric', '=', Decimal('1.1')),
                    ])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([
                    ('numeric', '!=', Decimal('1.1'))])
            self.assertEqual(props, [prop_b, prop_c])

            props = self.property_.search([
                    ('numeric', '<', Decimal('2.6')),
                    ])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([
                    ('numeric', '<=', Decimal('2.6'))])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([
                    ('numeric', '>', Decimal('1.1')),
                    ])
            self.assertEqual(props, [prop_b])

            props = self.property_.search([
                    ('numeric', '>=', Decimal('1.1'))])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([
                    ('numeric', 'in', [Decimal('1.1')])])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([
                    ('numeric', 'in', [Decimal('1.1'), Decimal('2.6')])])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([
                    ('numeric', 'not in', [Decimal('1.1')])])
            self.assertEqual(props, [prop_b, prop_c])

            props = self.property_.search([
                    ('numeric', 'not in', [Decimal('1.1'), Decimal('2.6')])])
            self.assertEqual(props, [prop_c])

            # Test default value
            property_field, = self.model_field.search([
                    ('model.model', '=', 'test.property'),
                    ('name', '=', 'numeric'),
                    ], limit=1)
            self.ir_property.create([{
                        'field': property_field.id,
                        'value': ',3.7',
                        }])

            prop_d, = self.property_.create([{}])
            self.assert_(prop_d)
            self.assertEqual(prop_d.numeric, Decimal('3.7'))

            self.property_.write([prop_a], {'numeric': None})
            self.assertEqual(prop_a.numeric, None)

            self.property_.write([prop_b], {'numeric': Decimal('3.11')})
            self.assertEqual(prop_b.numeric, Decimal('3.11'))

            transaction.cursor.rollback()

            # Test Selection
            prop_a, = self.property_.create([{'selection': 'option_a'}])
            self.assert_(prop_a)
            self.assertEqual(prop_a.selection, 'option_a')

            prop_b, = self.property_.create([{'selection': 'option_b'}])
            self.assert_(prop_b)
            self.assertEqual(prop_b.selection, 'option_b')

            prop_c, = self.property_.create([{}])
            self.assert_(prop_c)
            self.assertEqual(prop_c.selection, None)

            props = self.property_.search([('selection', '=', 'option_a')])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([('selection', '!=', None)])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([('selection', '=', None)])
            self.assertEqual(props, [prop_c])

            props = self.property_.search([('selection', '!=', 'option_a')])
            self.assertEqual(props, [prop_b, prop_c])

            props = self.property_.search([
                    ('selection', 'in', ['option_a'])])
            self.assertEqual(props, [prop_a])

            props = self.property_.search([
                    ('selection', 'in', ['option_a', 'option_b'])])
            self.assertEqual(props, [prop_a, prop_b])

            props = self.property_.search([
                    ('selection', 'not in', ['option_a'])])
            self.assertEqual(props, [prop_b, prop_c])

            # Test default value
            property_field, = self.model_field.search([
                    ('model.model', '=', 'test.property'),
                    ('name', '=', 'selection'),
                    ], limit=1)
            self.ir_property.create([{
                        'field': property_field.id,
                        'value': ',option_a',
                        }])

            prop_d, = self.property_.create([{}])
            self.assert_(prop_d)
            self.assertEqual(prop_d.selection, 'option_a')

            self.property_.write([prop_a], {'selection': None})
            self.assertEqual(prop_a.selection, None)

            self.property_.write([prop_c], {'selection': 'option_b'})
            self.assertEqual(prop_c.selection, 'option_b')

            transaction.cursor.rollback()

    def test_0160selection(self):
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            selection1, = self.selection.create([{'select': 'arabic'}])
            self.assert_(selection1)
            self.assertEqual(selection1.select, 'arabic')

            selection2, = self.selection.create([{'select': None}])
            self.assert_(selection2)
            self.assertEqual(selection2.select, None)

            self.assertRaises(Exception, self.selection.create,
                [{'select': 'chinese'}])

            selection3, = self.selection.create(
                [{'select': 'arabic', 'dyn_select': '1'}])
            self.assert_(selection3)
            self.assertEqual(selection3.select, 'arabic')
            self.assertEqual(selection3.dyn_select, '1')

            selection4, = self.selection.create(
                [{'select': 'hexa', 'dyn_select': '0x3'}])
            self.assert_(selection4)
            self.assertEqual(selection4.select, 'hexa')
            self.assertEqual(selection4.dyn_select, '0x3')

            selection5, = self.selection.create(
                [{'select': 'hexa', 'dyn_select': None}])
            self.assert_(selection5)
            self.assertEqual(selection5.select, 'hexa')
            self.assertEqual(selection5.dyn_select, None)

            self.assertRaises(Exception, self.selection.create,
                [{'select': 'arabic', 'dyn_select': '0x3'}])
            self.assertRaises(Exception, self.selection.create,
                [{'select': 'hexa', 'dyn_select': '3'}])

            self.assertRaises(Exception, self.selection_required.create, [{}])
            transaction.cursor.rollback()

            self.assertRaises(Exception, self.selection_required.create,
                [{'select': None}])
            transaction.cursor.rollback()

            selection6, = self.selection_required.create([{'select': 'latin'}])
            self.assert_(selection6)
            self.assertEqual(selection6.select, 'latin')

    def test0170dict(self):
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            dict1, = self.dict_.create([{
                        'dico': {'a': 1, 'b': 2},
                        }])
            self.assert_(dict1.dico == {'a': 1, 'b': 2})

            self.dict_.write([dict1], {'dico': {'z': 26}})
            self.assert_(dict1.dico == {'z': 26})

            dict2, = self.dict_.create([{}])
            self.assert_(dict2.dico is None)

            dict3, = self.dict_default.create([{}])
            self.assert_(dict3.dico == {'a': 1})

            self.assertRaises(Exception, self.dict_required.create, [{}])
            transaction.cursor.rollback()

            dict4, = self.dict_required.create([{'dico': dict(a=1)}])
            self.assert_(dict4.dico == {'a': 1})

            self.assertRaises(Exception, self.dict_required.create,
                [{'dico': {}}])
            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldsTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
