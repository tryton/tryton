#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import time
from decimal import Decimal
from trytond import pysocket
from trytond.tools import reduce_ids, safe_eval
from lxml import etree

ADMIN_PASSWORD = 'admin'
HOST = '127.0.0.1'
PORT = '8070'
DB_NAME = 'test_' + str(int(time.time()))
USERNAME = 'admin'
PASSWORD = 'admin'
CONTEXT = {}
USER = None
SESSION = None

SOCK = pysocket.PySocket()
SOCK.connect(HOST, PORT)

class DBTestCase(unittest.TestCase):
    '''
    Test DB service.
    '''

    def test0010create(self):
        '''
        Create database.
        '''
        SOCK.send((None, None, None, 'common', 'db', 'create', DB_NAME,
            ADMIN_PASSWORD, 'en_US', PASSWORD))
        res = SOCK.receive()
        self.assert_(res)

    def test0020list(self):
        '''
        List databases.
        '''
        SOCK.send((None, None, None, 'common', 'db', 'list'))
        res = SOCK.receive()
        self.assert_(DB_NAME in res)

    def test0030login(self):
        '''
        Login.
        '''
        login()


class ToolsTestCase(unittest.TestCase):
    '''
    Test tools.
    '''

    def test0000reduce_ids_empty(self):
        '''
        Test reduce_ids empty list.
        '''
        self.assert_(('(%s)', [False]) == reduce_ids('id', []))

    def test0010reduce_ids_continue(self):
        '''
        Test reduce_ids continue list.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)))', [0, 9]) == \
                reduce_ids('id', range(10)))

    def test0020reduce_ids_one_hole(self):
        '''
        Test reduce_ids continue list with one hole.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR ' \
                '((id >= %s) AND (id <= %s)))', [0, 9, 20, 29]) == \
                reduce_ids('id', range(10) + map(lambda x: x + 20, range(10))))

    def test0030reduce_ids_short_continue(self):
        '''
        Test reduce_ids short continue list.
        '''
        self.assert_(('((id IN (%s,%s,%s,%s)))', [0, 1, 2, 3]) == \
                reduce_ids('id', range(4)))

    def test0040reduce_ids_complex(self):
        '''
        Test reduce_ids complex list.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR ' \
                '(id IN (%s,%s,%s,%s,%s)))', [0, 14, 25, 26, 27, 28, 29]) == \
                reduce_ids('id', range(10) + map(lambda x: x + 25, range(5)) + \
                map(lambda x: x + 5, range(10))))

    def test0050reduce_ids_complex_small_continue(self):
        '''
        Test reduce_ids complex list with small continue.
        '''
        self.assert_(('(((id >= %s) AND (id <= %s)) OR (id IN (%s,%s,%s,%s)))',
            [1, 12, 15, 18, 19, 21]) == \
                    reduce_ids('id', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15,
                        18, 19, 21]))

    def test0060safe_eval_builtin(self):
        '''
        Attempt to access a unsafe builtin.
        '''
        self.assertRaises(Exception, safe_eval, "open('test.txt', 'w')")

    def test0061safe_eval_getattr(self):
        '''
        Attempt to get arround direct attr access.
        '''
        self.assertRaises(Exception, safe_eval, "getattr(int, '__abs__')")

    def test0062safe_eval_func_globals(self):
        '''
        Attempt to access global enviroment where fun was defined.
        '''
        self.assertRaises(Exception, safe_eval,
                "def x(): pass; print x.func_globals")

    def test0063safe_eval_lowlevel(self):
        '''
        Lowlevel tricks to access 'object'.
        '''
        self.assertRaises(Exception, safe_eval,
                "().__class__.mro()[1].__subclasses__()")


class FieldsTestCase(unittest.TestCase):
    '''
    Test Fields.
    '''

    def setUp(self):
        install_module('tests')
        self.boolean = RPCProxy('tests.boolean')
        self.boolean_default = RPCProxy('tests.boolean_default')

        self.integer = RPCProxy('tests.integer')
        self.integer_default = RPCProxy('tests.integer_default')
        self.integer_required = RPCProxy('tests.integer_required')

        self.float = RPCProxy('tests.float')
        self.float_default = RPCProxy('tests.float_default')
        self.float_required = RPCProxy('tests.float_required')

        self.numeric = RPCProxy('tests.numeric')
        self.numeric_default = RPCProxy('tests.numeric_default')
        self.numeric_required = RPCProxy('tests.numeric_required')

        self.char = RPCProxy('tests.char')
        self.char_default = RPCProxy('tests.char_default')
        self.char_required = RPCProxy('tests.char_required')
        self.char_size = RPCProxy('tests.char_size')

        self.text = RPCProxy('tests.text')
        self.text_default = RPCProxy('tests.text_default')
        self.text_required = RPCProxy('tests.text_required')
        self.text_size = RPCProxy('tests.text_size')

        self.sha = RPCProxy('tests.sha')
        self.sha_default = RPCProxy('tests.sha_default')
        self.sha_required = RPCProxy('tests.sha_required')

    def test0010boolean(self):
        '''
        Test Boolean.
        '''
        boolean1_id = self.boolean.create({
            'boolean': True,
            }, CONTEXT)
        self.assert_(boolean1_id)

        boolean1 = self.boolean.read(boolean1_id, ['boolean'], CONTEXT)
        self.assert_(boolean1['boolean'] == True)

        boolean_ids = self.boolean.search([
            ('boolean', '=', True),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search([
            ('boolean', '!=', True),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [True]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [True]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean2_id = self.boolean.create({
            'boolean': False,
            }, CONTEXT)
        self.assert_(boolean2_id)

        boolean2 = self.boolean.read(boolean2_id, ['boolean'], CONTEXT)
        self.assert_(boolean2['boolean'] == False)

        boolean_ids = self.boolean.search([
            ('boolean', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean2_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [True, False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [boolean1_id, boolean2_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [True, False]),
            ], 0, None, None, CONTEXT)
        self.assert_(boolean_ids == [])

        boolean3_id = self.boolean.create({}, CONTEXT)
        self.assert_(boolean3_id)

        boolean3 = self.boolean.read(boolean3_id, ['boolean'], CONTEXT)
        self.assert_(boolean3['boolean'] == False)

        boolean4_id = self.boolean_default.create({}, CONTEXT)
        self.assert_(boolean4_id)

        boolean4 = self.boolean_default.read(boolean4_id, ['boolean'], CONTEXT)
        self.assert_(boolean4['boolean'] == True)

        self.boolean.write(boolean1_id, {
            'boolean': False,
            }, CONTEXT)
        boolean1 = self.boolean.read(boolean1_id, ['boolean'], CONTEXT)
        self.assert_(boolean1['boolean'] == False)

        self.boolean.write(boolean2_id, {
            'boolean': True,
            }, CONTEXT)
        boolean2 = self.boolean.read(boolean2_id, ['boolean'], CONTEXT)
        self.assert_(boolean2['boolean'] == True)

    def test0020integer(self):
        '''
        Test Integer.
        '''
        integer1_id = self.integer.create({
            'integer': 1,
            }, CONTEXT)
        self.assert_(integer1_id)

        integer1 = self.integer.read(integer1_id, ['integer'], CONTEXT)
        self.assert_(integer1['integer'] == 1)

        integer_ids = self.integer.search([
            ('integer', '=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '!=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '!=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'not in', [1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'not in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>=', 1),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer2_id = self.integer.create({
            'integer': 0,
            }, CONTEXT)
        self.assert_(integer2_id)

        integer2 = self.integer.read(integer2_id, ['integer'], CONTEXT)
        self.assert_(integer2['integer'] == 0)

        integer_ids = self.integer.search([
            ('integer', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer2_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [0, 1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [integer1_id, integer2_id])

        integer_ids = self.integer.search([
            ('integer', 'not in', [0, 1]),
            ], 0, None, None, CONTEXT)
        self.assert_(integer_ids == [])

        integer3_id = self.integer.create({}, CONTEXT)
        self.assert_(integer3_id)

        integer3 = self.integer.read(integer3_id, ['integer'], CONTEXT)
        self.assert_(integer3['integer'] == 0)

        integer4_id = self.integer_default.create({}, CONTEXT)
        self.assert_(integer4_id)

        integer4 = self.integer_default.read(integer4_id, ['integer'], CONTEXT)
        self.assert_(integer4['integer'] == 5)

        self.integer.write(integer1_id, {
            'integer': 0,
            }, CONTEXT)
        integer1 = self.integer.read(integer1_id, ['integer'], CONTEXT)
        self.assert_(integer1['integer'] == 0)

        self.integer.write(integer2_id, {
            'integer': 1,
            }, CONTEXT)
        integer2 = self.integer.read(integer2_id, ['integer'], CONTEXT)
        self.assert_(integer2['integer'] == 1)

        self.failUnlessRaises(Exception, self.integer.create, {
            'integer': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.integer.write, integer1_id, {
            'integer': 'test',
            }, CONTEXT)

        integer5_id = self.integer_required.create({}, CONTEXT)
        self.assert_(integer5_id)

        integer5 = self.integer_required.read(integer5_id, ['integer'], CONTEXT)
        self.assert_(integer5['integer'] == 0)

    def test0030float(self):
        '''
        Test Float.
        '''
        float1_id = self.float.create({
            'float': 1.1,
            }, CONTEXT)
        self.assert_(float1_id)

        float1 = self.float.read(float1_id, ['float'], CONTEXT)
        self.assert_(float1['float'] == 1.1)

        float_ids = self.float.search([
            ('float', '=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '!=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '!=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'in', [1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'not in', [1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'not in', [0]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>=', 5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>=', -5),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>=', 1.1),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id])

        float2_id = self.float.create({
            'float': 0,
            }, CONTEXT)
        self.assert_(float2_id)

        float2 = self.float.read(float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 0)

        float_ids = self.float.search([
            ('float', '=', 0),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float2_id])

        float_ids = self.float.search([
            ('float', 'in', [0, 1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [float1_id, float2_id])

        float_ids = self.float.search([
            ('float', 'not in', [0, 1.1]),
            ], 0, None, None, CONTEXT)
        self.assert_(float_ids == [])

        float3_id = self.float.create({}, CONTEXT)
        self.assert_(float3_id)

        float3 = self.float.read(float3_id, ['float'], CONTEXT)
        self.assert_(float3['float'] == 0)

        float4_id = self.float_default.create({}, CONTEXT)
        self.assert_(float4_id)

        float4 = self.float_default.read(float4_id, ['float'], CONTEXT)
        self.assert_(float4['float'] == 5.5)

        self.float.write(float1_id, {
            'float': 0,
            }, CONTEXT)
        float1 = self.float.read(float1_id, ['float'] , CONTEXT)
        self.assert_(float1['float'] == 0)

        self.float.write(float2_id, {
            'float': 1.1,
            }, CONTEXT)
        float2 = self.float.read(float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 1.1)

        self.failUnlessRaises(Exception, self.float.create, {
            'float': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.float.write, float1_id, {
            'float': 'test',
            }, CONTEXT)

        float5_id = self.float_required.create({}, CONTEXT)
        self.assert_(float5_id)

        float5 = self.float_required.read(float5_id, ['float'], CONTEXT)
        self.assert_(float5['float'] == 0)

    def test0040numeric(self):
        '''
        Test Numeric.
        '''
        numeric1_id = self.numeric.create({
            'numeric': Decimal('1.1'),
            }, CONTEXT)
        self.assert_(numeric1_id)

        numeric1 = self.numeric.read(numeric1_id, ['numeric'], CONTEXT)
        self.assert_(numeric1['numeric'] == Decimal('1.1'))

        numeric_ids = self.numeric.search([
            ('numeric', '=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '!=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '!=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', 'in', [Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', 'in', [Decimal('0')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', 'not in', [Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', 'not in', [Decimal('0')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '<', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '<', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '<', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '<=', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '<=', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '<=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '>', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '>', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '>', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '>=', Decimal('5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric_ids = self.numeric.search([
            ('numeric', '>=', Decimal('-5')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric_ids = self.numeric.search([
            ('numeric', '>=', Decimal('1.1')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id])

        numeric2_id = self.numeric.create({
            'numeric': Decimal('0'),
            }, CONTEXT)
        self.assert_(numeric2_id)

        numeric2 = self.numeric.read(numeric2_id, ['numeric'], CONTEXT)
        self.assert_(numeric2['numeric'] == Decimal('0'))

        numeric_ids = self.numeric.search([
            ('numeric', '=', Decimal('0')),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric2_id])

        numeric_ids = self.numeric.search([
            ('numeric', 'in', [Decimal('0'), Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [numeric1_id, numeric2_id])

        numeric_ids = self.numeric.search([
            ('numeric', 'not in', [Decimal('0'), Decimal('1.1')]),
            ], 0, None, None, CONTEXT)
        self.assert_(numeric_ids == [])

        numeric3_id = self.numeric.create({}, CONTEXT)
        self.assert_(numeric3_id)

        numeric3 = self.numeric.read(numeric3_id, ['numeric'], CONTEXT)
        self.assert_(numeric3['numeric'] == Decimal('0'))

        numeric4_id = self.numeric_default.create({}, CONTEXT)
        self.assert_(numeric4_id)

        numeric4 = self.numeric_default.read(numeric4_id, ['numeric'], CONTEXT)
        self.assert_(numeric4['numeric'] == Decimal('5.5'))

        self.numeric.write(numeric1_id, {
            'numeric': Decimal('0'),
            }, CONTEXT)
        numeric1 = self.numeric.read(numeric1_id, ['numeric'] , CONTEXT)
        self.assert_(numeric1['numeric'] == Decimal('0'))

        self.numeric.write(numeric2_id, {
            'numeric': Decimal('1.1'),
            }, CONTEXT)
        numeric2 = self.numeric.read(numeric2_id, ['numeric'], CONTEXT)
        self.assert_(numeric2['numeric'] == Decimal('1.1'))

        self.failUnlessRaises(Exception, self.numeric.create, {
            'numeric': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.numeric.write, numeric1_id, {
            'numeric': 'test',
            }, CONTEXT)

        numeric5_id = self.numeric_required.create({}, CONTEXT)
        self.assert_(numeric5_id)

        numeric5 = self.numeric_required.read(numeric5_id, ['numeric'], CONTEXT)
        self.assert_(numeric5['numeric'] == Decimal('0'))

    def test0050char(self):
        '''
        Test Char.
        '''
        char1_id = self.char.create({
            'char': 'Test',
            }, CONTEXT)
        self.assert_(char1_id)

        char1 = self.char.read(char1_id, ['char'], CONTEXT)
        self.assert_(char1['char'] == 'Test')

        char_ids = self.char.search([
            ('char', '=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', '=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', '!=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', '!=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'like', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'like', 'T%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'ilike', 'test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'ilike', 't%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not like', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not like', 'T%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'not like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'not ilike', 'test'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not ilike', 't%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char_ids = self.char.search([
            ('char', 'not ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char_ids = self.char.search([
            ('char', 'not ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id])

        char2_id = self.char.create({
            'char': False,
            }, CONTEXT)
        self.assert_(char2_id)

        char2 = self.char.read(char2_id, ['char'], CONTEXT)
        self.assert_(char2['char'] == None)

        char_ids = self.char.search([
            ('char', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char2_id])

        char_ids = self.char.search([
            ('char', 'in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [char1_id, char2_id])

        char_ids = self.char.search([
            ('char', 'not in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(char_ids == [])

        char3_id = self.char.create({}, CONTEXT)
        self.assert_(char3_id)

        char3 = self.char.read(char3_id, ['char'], CONTEXT)
        self.assert_(char3['char'] == None)

        char4_id = self.char_default.create({}, CONTEXT)
        self.assert_(char4_id)

        char4 = self.char_default.read(char4_id, ['char'], CONTEXT)
        self.assert_(char4['char'] == 'Test')

        self.char.write(char1_id, {
            'char': False,
            }, CONTEXT)
        char1 = self.char.read(char1_id, ['char'], CONTEXT)
        self.assert_(char1['char'] == None)

        self.char.write(char2_id, {
            'char': 'Test',
            }, CONTEXT)
        char2 = self.char.read(char2_id, ['char'], CONTEXT)
        self.assert_(char2['char'] == 'Test')

        self.failUnlessRaises(Exception, self.char_required.create, {}, CONTEXT)

        char5_id = self.char_required.create({
            'char': 'Test',
            }, CONTEXT)
        self.assert_(char5_id)

        char6_id = self.char_size.create({
            'char': 'Test',
            }, CONTEXT)
        self.assert_(char6_id)

        self.failUnlessRaises(Exception, self.char_size.create, {
            'char': 'foobar',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.char_size.write, char6_id, {
            'char': 'foobar',
            }, CONTEXT)

    def test0060text(self):
        '''
        Test Text.
        '''
        text1_id = self.text.create({
            'text': 'Test',
            }, CONTEXT)
        self.assert_(text1_id)

        text1 = self.text.read(text1_id, ['text'], CONTEXT)
        self.assert_(text1['text'] == 'Test')

        text_ids = self.text.search([
            ('text', '=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', '=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', '!=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', '!=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'like', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'like', 'T%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'ilike', 'test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'ilike', 't%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not like', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not like', 'T%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'not like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'not ilike', 'test'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not ilike', 't%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text_ids = self.text.search([
            ('text', 'not ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text_ids = self.text.search([
            ('text', 'not ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id])

        text2_id = self.text.create({
            'text': False,
            }, CONTEXT)
        self.assert_(text2_id)

        text2 = self.text.read(text2_id, ['text'], CONTEXT)
        self.assert_(text2['text'] == None)

        text_ids = self.text.search([
            ('text', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text2_id])

        text_ids = self.text.search([
            ('text', 'in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [text1_id, text2_id])

        text_ids = self.text.search([
            ('text', 'not in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(text_ids == [])

        text3_id = self.text.create({}, CONTEXT)
        self.assert_(text3_id)

        text3 = self.text.read(text3_id, ['text'], CONTEXT)
        self.assert_(text3['text'] == None)

        text4_id = self.text_default.create({}, CONTEXT)
        self.assert_(text4_id)

        text4 = self.text_default.read(text4_id, ['text'], CONTEXT)
        self.assert_(text4['text'] == 'Test')

        self.text.write(text1_id, {
            'text': False,
            }, CONTEXT)
        text1 = self.text.read(text1_id, ['text'], CONTEXT)
        self.assert_(text1['text'] == None)

        self.text.write(text2_id, {
            'text': 'Test',
            }, CONTEXT)
        text2 = self.text.read(text2_id, ['text'], CONTEXT)
        self.assert_(text2['text'] == 'Test')

        self.failUnlessRaises(Exception, self.text_required.create, {}, CONTEXT)

        text5_id = self.text_required.create({
            'text': 'Test',
            }, CONTEXT)
        self.assert_(text5_id)

        text6_id = self.text_size.create({
            'text': 'Test',
            }, CONTEXT)
        self.assert_(text6_id)

        self.failUnlessRaises(Exception, self.text_size.create, {
            'text': 'foobar',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.text_size.write, text6_id, {
            'text': 'foobar',
            }, CONTEXT)

        text7_id = self.text.create({
            'text': 'Foo\nBar',
            }, CONTEXT)
        self.assert_(text7_id)

    def test0070sha(self):
        '''
        Test Sha.
        '''
        sha1_id = self.sha.create({
            'sha': 'Test',
            }, CONTEXT)
        self.assert_(sha1_id)

        sha1 = self.sha.read(sha1_id, ['sha'], CONTEXT)
        self.assert_(sha1['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

        sha_ids = self.sha.search([
            ('sha', '=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', '=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', '!=', 'Test'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', '!=', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', '!=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not in', ['Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not in', ['Foo']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'not in', [False]),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'not in', []),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'like', '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'like', '640a%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'ilike', '640AB2BAE07BEDC4C163F679A746F7AB7FB5D1FA'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'ilike', '640A%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not like', '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not like', '640a%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not like', 'Foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'not like', 'F%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'not ilike', '640AB2BAE07BEDC4C163F679A746F7AB7FB5D1FA'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not ilike', '640A%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha_ids = self.sha.search([
            ('sha', 'not ilike', 'foo'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha_ids = self.sha.search([
            ('sha', 'not ilike', 'f%'),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id])

        sha2_id = self.sha.create({
            'sha': False,
            }, CONTEXT)
        self.assert_(sha2_id)

        sha2 = self.sha.read(sha2_id, ['sha'], CONTEXT)
        self.assert_(sha2['sha'] == None)

        sha_ids = self.sha.search([
            ('sha', '=', False),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha2_id])

        sha_ids = self.sha.search([
            ('sha', 'in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [sha1_id, sha2_id])

        sha_ids = self.sha.search([
            ('sha', 'not in', [False, 'Test']),
            ], 0, None, None, CONTEXT)
        self.assert_(sha_ids == [])

        sha3_id = self.sha.create({}, CONTEXT)
        self.assert_(sha3_id)

        sha3 = self.sha.read(sha3_id, ['sha'], CONTEXT)
        self.assert_(sha3['sha'] == None)

        sha4_id = self.sha_default.create({}, CONTEXT)
        self.assert_(sha4_id)

        sha4 = self.sha_default.read(sha4_id, ['sha'], CONTEXT)
        self.assert_(sha4['sha'] == 'ba79baeb9f10896a46ae74715271b7f586e74640')

        self.sha.write(sha1_id, {
            'sha': False,
            }, CONTEXT)
        sha1 = self.sha.read(sha1_id, ['sha'], CONTEXT)
        self.assert_(sha1['sha'] == None)

        self.sha.write(sha2_id, {
            'sha': 'Test',
            }, CONTEXT)
        sha2 = self.sha.read(sha2_id, ['sha'], CONTEXT)
        self.assert_(sha2['sha'] == '640ab2bae07bedc4c163f679a746f7ab7fb5d1fa')

        self.failUnlessRaises(Exception, self.sha_required.create, {}, CONTEXT)

        sha5_id = self.sha_required.create({
            'sha': 'Test',
            }, CONTEXT)
        self.assert_(sha5_id)


class ModelViewTestCase(unittest.TestCase):
    '''
    Test ModelView
    '''

    def setUp(self):
        install_module('ir')
        install_module('res')
        install_module('workflow')
        install_module('webdav')

    def test0010ir(self):
        '''
        Test ir.
        '''
        test_view('ir')

    def test0020res(self):
        '''
        Test res.
        '''
        test_view('res')

    def test0030workflow(self):
        '''
        Test workflow.
        '''
        test_view('workflow')

    def test0040webdav(self):
        '''
        Test webdav.
        '''
        test_view('webdav')


class ModelSingletonTestCase(unittest.TestCase):
    '''
    Test ModelSingleton
    '''

    def setUp(self):
        install_module('tests')
        self.singleton = RPCProxy('tests.singleton')

    def test0010read(self):
        '''
        Test read method.
        '''
        singleton = self.singleton.read(1, ['name'], CONTEXT)
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

        singleton = self.singleton.read([1], ['name'], CONTEXT)[0]
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

    def test0020create(self):
        '''
        Test create method.
        '''
        singleton_id = self.singleton.create({'name': 'bar'}, CONTEXT)
        self.assert_(singleton_id)

        singleton = self.singleton.read(singleton_id, ['name'], CONTEXT)
        self.assert_(singleton['name'] == 'bar')

        singleton2_id = self.singleton.create({'name': 'foo'}, CONTEXT)
        self.assert_(singleton2_id == singleton_id)

        singleton = self.singleton.read(singleton_id, ['name'], CONTEXT)
        self.assert_(singleton['name'] == 'foo')

        singleton_ids = self.singleton.search([], 0, None, None, CONTEXT)
        self.assert_(len(singleton_ids) == 1)

    def test0030copy(self):
        '''
        Test copy method.
        '''
        singleton_id = self.singleton.search([], 0, None, None, CONTEXT)[0]

        singleton2_id = self.singleton.copy(singleton_id, None, CONTEXT)
        self.assert_(singleton2_id == singleton_id)

        singleton_ids = self.singleton.search([], 0, None, None, CONTEXT)
        self.assert_(len(singleton_ids) == 1)

        singleton3_id = self.singleton.copy(singleton_id, {'name': 'bar'},
                CONTEXT)
        self.assert_(singleton3_id == singleton_id)

        singleton_ids = self.singleton.search([], 0, None, None, CONTEXT)
        self.assert_(len(singleton_ids) == 1)

    def test0040default_get(self):
        '''
        Test default_get method.
        '''
        self.singleton.delete(self.singleton.search([], 0, None, None,
            CONTEXT), CONTEXT)

        default = self.singleton.default_get(['name'], CONTEXT)
        self.assert_(default == {'name': 'test'})

        default = self.singleton.default_get(['create_uid'], CONTEXT)
        self.assert_(len(default) == 2)

        default = self.singleton.default_get(['create_uid'], CONTEXT, False)
        self.assert_(len(default) == 1)

        singleton_id = self.singleton.create({'name': 'bar'}, CONTEXT)

        default = self.singleton.default_get(['name'], CONTEXT)
        self.assert_(default == {'name': 'bar'})

        default = self.singleton.default_get(['create_uid'], CONTEXT)
        self.assert_(len(default) == 2)

        default = self.singleton.default_get(['create_uid'], CONTEXT, False)
        self.assert_(len(default) == 1)

    def test0050search(self):
        '''
        Test search method.
        '''
        self.singleton.delete(self.singleton.search([], 0, None, None,
            CONTEXT), CONTEXT)

        singleton_ids = self.singleton.search([], 0, None, None, CONTEXT)
        self.assert_(singleton_ids == [1])

        singleton_ids = self.singleton.search([], 0, 1, None, CONTEXT)
        self.assert_(singleton_ids == [1])

        singleton_ids = self.singleton.search([], 0, None, None, CONTEXT, True)
        self.assert_(singleton_ids == 1)


class MPTTTestCase(unittest.TestCase):
    '''
    Test Modified Preorder Tree Traversal.
    '''

    def setUp(self):
        install_module('tests')
        self.mptt = RPCProxy('tests.mptt')

    def CheckTree(self, parent_id=False, left=0, right=0):
        child_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        childs = self.mptt.read(child_ids, ['left', 'right'], CONTEXT)
        childs.sort(lambda x, y: cmp(child_ids.index(x['id']),
            child_ids.index(y['id'])))
        for child in childs:
            assert child['left'] > left, \
                    'Record (%d): left %d <= parent left %d' % \
                    (child['id'], child['left'], left)
            assert child['left'] < child['right'], \
                    'Record (%d): left %d >= right %d' % \
                    (child['id'], child['left'], child['right'])
            assert right == 0 or child['right'] < right, \
                    'Record (%d): right %d >= parent right %d' % \
                    (child['id'], child['right'], right)
            self.CheckTree(child['id'], left=child['left'],
                    right=child['right'])
        next_left = 0
        for child in childs:
            assert child['left'] > next_left, \
                    'Record (%d): left %d <= next left %d' % \
                    (child['id'], child['left'], next_left)
            next_left = child['right']
        childs.reverse()
        previous_right = 0
        for child in childs:
            assert previous_right == 0 or child['right'] < previous_right, \
                    'Record (%d): right %d >= previous right %d' % \
                    (child['id'] , child['right'], previous_right)
            previous_right = child['left']


    def ReParent(self, parent_id=False):
        record_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        if not record_ids:
            return
        for record_id in record_ids:
            for record2_id in record_ids:
                if record_id != record2_id:
                    self.mptt.write(record_id, {
                        'parent': record2_id,
                        }, CONTEXT)
                    self.CheckTree()
                    self.mptt.write(record_id, {
                        'parent': parent_id,
                        }, CONTEXT)
                    self.CheckTree()
        for record_id in record_ids:
            self.ReParent(record_id)

    def ReOrder(self, parent_id=False):
        record_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        if not record_ids:
            return
        i = len(record_ids)
        for record_id in record_ids:
            self.mptt.write(record_id, {
                'sequence': i,
                }, CONTEXT)
            i -= 1
            self.CheckTree()
        i = 0
        for record_id in record_ids:
            self.mptt.write(record_id, {
                'sequence': i,
                }, CONTEXT)
            i += 1
            self.CheckTree()
        for record_id in record_ids:
            self.ReOrder(record_id)

        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        self.mptt.write(record_ids, {
            'sequence': 0,
            }, CONTEXT)
        self.CheckTree()

    def test0010create(self):
        '''
        Create tree.
        '''
        new_records = [False]
        for j in range(3):
            parent_records = new_records
            new_records = []
            k = 0
            for parent_record in parent_records:
                for i in range(3):
                    record_id = self.mptt.create({
                        'name': 'Test %d %d %d' % (j, k, i),
                        'parent': parent_record,
                        }, CONTEXT)
                    new_records.append(record_id)
                k += 1
        self.CheckTree()

    def test0020reorder(self):
        '''
        Re-order.
        '''
        self.ReOrder()

    def test0030reparent(self):
        '''
        Re-parent.
        '''
        self.ReParent()

    def test0040active(self):
        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.write(record_id, {
                        'active': False
                        }, CONTEXT)
                self.CheckTree()

        self.ReParent()
        self.ReOrder()

        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        self.mptt.write(record_ids[:len(record_ids)/2], {
                'active': False
                }, CONTEXT)
        self.CheckTree()
        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        self.mptt.write(record_ids, {
                'active': False
                }, CONTEXT)


        self.ReParent()
        self.ReOrder()

        record_ids = self.mptt.search([
                ('active', '=', False),
                ], 0, None, None, CONTEXT)
        self.mptt.write(record_ids, {
                'active': False
                }, CONTEXT)
        self.CheckTree()

    def test0050delete(self):
        '''
        Delete.
        '''
        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.delete(record_id, CONTEXT)
                self.CheckTree()
        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        self.mptt.delete(record_ids[:len(record_ids)/2], CONTEXT)
        self.CheckTree()
        record_ids = self.mptt.search([], 0, None, None, CONTEXT)
        self.mptt.delete(record_ids, CONTEXT)
        self.CheckTree()


class RPCProxy(object):

    def __init__(self, name):
        self.name = name
        self.__attrs = {}

    def __getattr__(self, attr):
        if attr not in self.__attrs:
            self.__attrs[attr] = RPCFunction(self.name, attr)
        return self.__attrs[attr]


class RPCFunction(object):

    def __init__(self, name, func_name):
        self.name = name
        self.func_name = func_name

    def __call__(self, *args):
        SOCK.send((DB_NAME, USER, SESSION, 'model', self.name, self.func_name) \
                + args)
        res = SOCK.receive()
        return res

def login():
    global USER, SESSION, CONTEXT
    SOCK.send((DB_NAME, USERNAME, PASSWORD, 'common', 'db', 'login'))
    USER, SESSION = SOCK.receive()
    user = RPCProxy('res.user')
    context = user.get_preferences(True, {})
    for i in context:
        value = context[i]
        CONTEXT[i] = value

def install_module(name):
    module = RPCProxy('ir.module.module')
    module_ids = module.search([
        ('name', '=', name),
        ('state', '!=', 'installed'),
        ])

    if not module_ids:
        return

    module.button_install(module_ids, CONTEXT)

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'create'))
    wiz_id = SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'execute', wiz_id, {}, 'start',
        CONTEXT))
    SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'delete', wiz_id))
    SOCK.receive()

def test_view(module_name):
    view_obj = RPCProxy('ir.ui.view')
    view_ids = view_obj.search([
        ('module', '=', module_name),
        ])

    for view in view_obj.read(view_ids, ['id', 'model', 'inherit']):
        view_id = view['inherit'] or view['id']
        model = view['model']
        model_obj = RPCProxy(model)
        res = model_obj.fields_view_get(view_id)
        assert res['model'] == model
        tree = etree.fromstring(res['arch'])
        tree_root = tree.getroottree().getroot()

        def check_tree(element):
            if element.tag in ('field', 'label', 'separator', 'group'):
                for attr in ('name', 'icon'):
                    field = element.get(attr)
                    if field:
                        assert field in res['fields']
            for child in element:
                check_tree(child)
        check_tree(tree_root)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DBTestCase)

if __name__ == '__main__':
    suite = suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ToolsTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FieldsTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModelSingletonTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModelViewTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase))
    unittest.TextTestRunner(verbosity=2).run(suite)
    SOCK.disconnect()
