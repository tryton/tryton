# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from datetime import datetime
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class ModelSingletonTestCase(unittest.TestCase):
    'Test ModelSingleton'

    def setUp(self):
        install_module('tests')
        self.singleton = POOL.get('test.singleton')

    def test0010read(self):
        'Test read method'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton, = self.singleton.read([1], ['name'])
            self.assert_(singleton['name'] == 'test')
            self.assert_(singleton['id'] == 1)

            singleton, = self.singleton.read([1], ['name'])
            self.assert_(singleton['name'] == 'test')
            self.assert_(singleton['id'] == 1)

            singleton, = self.singleton.read([1], [
                'create_uid',
                'create_uid.rec_name',
                'create_date',
                'write_uid',
                'write_date',
                ])
            self.assertEqual(singleton['create_uid'], USER)
            self.assertEqual(singleton['create_uid.rec_name'], 'Administrator')
            self.assert_(isinstance(singleton['create_date'], datetime))
            self.assertEqual(singleton['write_uid'], None)
            self.assertEqual(singleton['write_date'], None)

            transaction.cursor.rollback()

    def test0020create(self):
        'Test create method'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton, = self.singleton.create([{'name': 'bar'}])
            self.assert_(singleton)
            self.assertEqual(singleton.name, 'bar')

            singleton2, = self.singleton.create([{'name': 'foo'}])
            self.assertEqual(singleton2, singleton)

            self.assertEqual(singleton.name, 'foo')

            singletons = self.singleton.search([])
            self.assertEqual(singletons, [singleton])

            transaction.cursor.rollback()

    def test0030copy(self):
        'Test copy method'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singleton, = self.singleton.search([])

            singleton2, = self.singleton.copy([singleton])
            self.assertEqual(singleton2, singleton)

            singletons = self.singleton.search([])
            self.assertEqual(len(singletons), 1)

            singleton3, = self.singleton.copy([singleton], {'name': 'bar'})
            self.assertEqual(singleton3, singleton)

            singletons = self.singleton.search([])
            self.assertEqual(len(singletons), 1)

            transaction.cursor.rollback()

    def test0040default_get(self):
        'Test default_get method'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            default = self.singleton.default_get(['name'])
            self.assertEqual(default, {'name': 'test'})

            default = self.singleton.default_get(['create_uid'])
            self.assertEqual(len(default), 2)

            default = self.singleton.default_get(['create_uid'],
                    with_rec_name=False)
            self.assertEqual(len(default), 1)

            self.singleton.create([{'name': 'bar'}])

            default = self.singleton.default_get(['name'])
            self.assertEqual(default, {'name': 'bar'})

            default = self.singleton.default_get(['create_uid'])
            self.assertEqual(len(default), 2)

            default = self.singleton.default_get(['create_uid'],
                    with_rec_name=False)
            self.assertEqual(len(default), 1)

            transaction.cursor.rollback()

    def test0050search(self):
        'Test search method'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            singletons = self.singleton.search([])
            self.assertEqual(map(int, singletons), [1])

            singletons = self.singleton.search([])
            self.assertEqual(map(int, singletons), [1])

            count = self.singleton.search([], count=True)
            self.assertEqual(count, 1)

            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSingletonTestCase)
