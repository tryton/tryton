# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from datetime import datetime
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool


class ModelSingletonTestCase(unittest.TestCase):
    'Test ModelSingleton'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_read(self):
        'Test read method'
        pool = Pool()
        Singleton = pool.get('test.singleton')

        singleton, = Singleton.read([1], ['name'])
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

        singleton, = Singleton.read([1], ['name'])
        self.assert_(singleton['name'] == 'test')
        self.assert_(singleton['id'] == 1)

        singleton, = Singleton.read([1], [
            'create_uid',
            'create_uid.rec_name',
            'create_date',
            'write_uid',
            'write_date',
            ])
        self.assertEqual(singleton['create_uid'], Transaction().user)
        self.assertEqual(singleton['create_uid.rec_name'], 'Administrator')
        self.assert_(isinstance(singleton['create_date'], datetime))
        self.assertEqual(singleton['write_uid'], None)
        self.assertEqual(singleton['write_date'], None)

    @with_transaction()
    def test_create(self):
        'Test create method'
        pool = Pool()
        Singleton = pool.get('test.singleton')

        singleton, = Singleton.create([{'name': 'bar'}])
        self.assert_(singleton)
        self.assertEqual(singleton.name, 'bar')

        singleton2, = Singleton.create([{'name': 'foo'}])
        self.assertEqual(singleton2, singleton)

        self.assertEqual(singleton.name, 'foo')

        singletons = Singleton.search([])
        self.assertEqual(singletons, [singleton])

    @with_transaction()
    def test_copy(self):
        'Test copy method'
        pool = Pool()
        Singleton = pool.get('test.singleton')

        singleton, = Singleton.search([])

        singleton2, = Singleton.copy([singleton])
        self.assertEqual(singleton2, singleton)

        singletons = Singleton.search([])
        self.assertEqual(len(singletons), 1)

        singleton3, = Singleton.copy([singleton], {'name': 'bar'})
        self.assertEqual(singleton3, singleton)

        singletons = Singleton.search([])
        self.assertEqual(len(singletons), 1)

    @with_transaction()
    def test_default_get(self):
        'Test default_get method'
        pool = Pool()
        Singleton = pool.get('test.singleton')

        default = Singleton.default_get(['name'])
        self.assertEqual(default, {'name': 'test'})

        default = Singleton.default_get(['create_uid'])
        self.assertEqual(len(default), 2)

        default = Singleton.default_get(['create_uid'],
                with_rec_name=False)
        self.assertEqual(len(default), 1)

        Singleton.create([{'name': 'bar'}])

        default = Singleton.default_get(['name'])
        self.assertEqual(default, {'name': 'bar'})

        default = Singleton.default_get(['create_uid'])
        self.assertEqual(len(default), 2)

        default = Singleton.default_get(['create_uid'],
                with_rec_name=False)
        self.assertEqual(len(default), 1)

    @with_transaction()
    def test_search(self):
        'Test search method'
        pool = Pool()
        Singleton = pool.get('test.singleton')

        singletons = Singleton.search([])
        self.assertEqual(map(int, singletons), [1])

        singletons = Singleton.search([])
        self.assertEqual(map(int, singletons), [1])

        count = Singleton.search([], count=True)
        self.assertEqual(count, 1)

        Singleton.create([{'name': 'foo'}])
        singleton, = Singleton.search([('name', '=', 'foo')])
        self.assertEqual(singleton.name, 'foo')
        singletons = Singleton.search([('name', '=', 'bar')])
        self.assertEqual(singletons, [])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSingletonTestCase)
