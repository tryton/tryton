#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from datetime import datetime
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


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
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton = self.singleton.read(1, ['name'])
            self.assert_(singleton['name'] == 'test')
            self.assert_(singleton['id'] == 1)

            singleton, = self.singleton.read([1], ['name'])
            self.assert_(singleton['name'] == 'test')
            self.assert_(singleton['id'] == 1)

            singleton = self.singleton.read(1, [
                'create_uid',
                'create_date',
                'write_uid',
                'write_date',
                ])
            self.assertEqual(singleton['create_uid'], USER)
            self.assert_(isinstance(singleton['create_date'], datetime))
            self.assertEqual(singleton['write_uid'], False)
            self.assertEqual(singleton['write_date'], False)

            transaction.cursor.rollback()

    def test0020create(self):
        '''
        Test create method.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton_id = self.singleton.create({'name': 'bar'})
            self.assert_(singleton_id)

            singleton = self.singleton.read(singleton_id, ['name'])
            self.assert_(singleton['name'] == 'bar')

            singleton2_id = self.singleton.create({'name': 'foo'})
            self.assert_(singleton2_id == singleton_id)

            singleton = self.singleton.read(singleton_id, ['name'])
            self.assert_(singleton['name'] == 'foo')

            singleton_ids = self.singleton.search([])
            self.assert_(len(singleton_ids) == 1)

            transaction.cursor.rollback()

    def test0030copy(self):
        '''
        Test copy method.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton_id = self.singleton.search([])[0]

            singleton2_id = self.singleton.copy(singleton_id)
            self.assert_(singleton2_id == singleton_id)

            singleton_ids = self.singleton.search([])
            self.assert_(len(singleton_ids) == 1)

            singleton3_id = self.singleton.copy(singleton_id, {'name': 'bar'})
            self.assert_(singleton3_id == singleton_id)

            singleton_ids = self.singleton.search([])
            self.assert_(len(singleton_ids) == 1)

            transaction.cursor.rollback()

    def test0040default_get(self):
        '''
        Test default_get method.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            default = self.singleton.default_get(['name'])
            self.assert_(default == {'name': 'test'})

            default = self.singleton.default_get(['create_uid'])
            self.assert_(len(default) == 2)

            default = self.singleton.default_get(['create_uid'],
                    with_rec_name=False)
            self.assert_(len(default) == 1)

            self.singleton.create({'name': 'bar'})

            default = self.singleton.default_get(['name'])
            self.assert_(default == {'name': 'bar'})

            default = self.singleton.default_get(['create_uid'])
            self.assert_(len(default) == 2)

            default = self.singleton.default_get(['create_uid'],
                    with_rec_name=False)
            self.assert_(len(default) == 1)

            transaction.cursor.rollback()

    def test0050search(self):
        '''
        Test search method.
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton_ids = self.singleton.search([])
            self.assert_(singleton_ids == [1])

            singleton_ids = self.singleton.search([])
            self.assert_(singleton_ids == [1])

            singleton_ids = self.singleton.search([], count=True)
            self.assert_(singleton_ids == 1)

            transaction.cursor.rollback()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSingletonTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
