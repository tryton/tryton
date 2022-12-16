#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
from datetime import datetime
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module


class ModelSingletonTestCase(unittest.TestCase):
    '''
    Test ModelSingleton
    '''

    def setUp(self):
        install_module('test')
        self.singleton = POOL.get('test.singleton')

    def test0010read(self):
        '''
        Test read method.
        '''
        cursor = DB.cursor()

        singleton = self.singleton.read(cursor, USER, 1, ['name'], CONTEXT)
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

        singleton = self.singleton.read(cursor, USER, [1], ['name'], CONTEXT)[0]
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

        singleton = self.singleton.read(cursor, USER, 1, [
            'create_uid',
            'create_date',
            'write_uid',
            'write_date',
            ], CONTEXT)
        self.assertEqual(singleton['create_uid'], USER)
        self.assert_(isinstance(singleton['create_date'], datetime))
        self.assertEqual(singleton['write_uid'], False)
        self.assertEqual(singleton['write_date'], False)

        cursor.rollback()
        cursor.close()

    def test0020create(self):
        '''
        Test create method.
        '''
        cursor = DB.cursor()

        singleton_id = self.singleton.create(cursor, USER, {'name': 'bar'},
                CONTEXT)
        self.assert_(singleton_id)

        singleton = self.singleton.read(cursor, USER, singleton_id, ['name'],
                CONTEXT)
        self.assert_(singleton['name'] == 'bar')

        singleton2_id = self.singleton.create(cursor, USER, {'name': 'foo'},
                CONTEXT)
        self.assert_(singleton2_id == singleton_id)

        singleton = self.singleton.read(cursor, USER, singleton_id, ['name'],
                CONTEXT)
        self.assert_(singleton['name'] == 'foo')

        singleton_ids = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT)
        self.assert_(len(singleton_ids) == 1)

        cursor.rollback()
        cursor.close()

    def test0030copy(self):
        '''
        Test copy method.
        '''
        cursor = DB.cursor()

        singleton_id = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT)[0]

        singleton2_id = self.singleton.copy(cursor, USER, singleton_id, None,
                CONTEXT)
        self.assert_(singleton2_id == singleton_id)

        singleton_ids = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT)
        self.assert_(len(singleton_ids) == 1)

        singleton3_id = self.singleton.copy(cursor, USER, singleton_id,
                {'name': 'bar'}, CONTEXT)
        self.assert_(singleton3_id == singleton_id)

        singleton_ids = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT)
        self.assert_(len(singleton_ids) == 1)

        cursor.rollback()
        cursor.close()

    def test0040default_get(self):
        '''
        Test default_get method.
        '''
        cursor = DB.cursor()

        default = self.singleton.default_get(cursor, USER, ['name'], CONTEXT)
        self.assert_(default == {'name': 'test'})

        default = self.singleton.default_get(cursor, USER, ['create_uid'],
                CONTEXT)
        self.assert_(len(default) == 2)

        default = self.singleton.default_get(cursor, USER, ['create_uid'],
                CONTEXT, False)
        self.assert_(len(default) == 1)

        self.singleton.create(cursor, USER, {'name': 'bar'}, CONTEXT)

        default = self.singleton.default_get(cursor, USER, ['name'], CONTEXT)
        self.assert_(default == {'name': 'bar'})

        default = self.singleton.default_get(cursor, USER, ['create_uid'],
                CONTEXT)
        self.assert_(len(default) == 2)

        default = self.singleton.default_get(cursor, USER, ['create_uid'],
                CONTEXT, False)
        self.assert_(len(default) == 1)

        cursor.rollback()
        cursor.close()

    def test0050search(self):
        '''
        Test search method.
        '''
        cursor = DB.cursor()

        singleton_ids = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT)
        self.assert_(singleton_ids == [1])

        singleton_ids = self.singleton.search(cursor, USER, [], 0, 1, None,
                CONTEXT)
        self.assert_(singleton_ids == [1])

        singleton_ids = self.singleton.search(cursor, USER, [], 0, None, None,
                CONTEXT, True)
        self.assert_(singleton_ids == 1)

        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSingletonTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
