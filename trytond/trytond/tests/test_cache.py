# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import os
import time
import unittest

from trytond import backend
from trytond import cache as cache_mod
from trytond.cache import (
    LRUDict, LRUDictTransaction, MemoryCache, freeze, unfreeze)
from trytond.tests.test_tryton import (
    DB_NAME, USER, activate_module, with_transaction)
from trytond.transaction import Transaction

cache = MemoryCache('test.cache')
cache_expire = MemoryCache('test.cache_expire', duration=1)
cache_ignored_local_context = MemoryCache(
    'test.cache.ignored.local', context_ignored_keys={'ignored'})
cache_ignored_global_context = MemoryCache('test.cache.ignored.global')


class CacheTestCase(unittest.TestCase):
    "Test Cache"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def testFreeze(self):
        "Test freeze"
        self.assertEqual(freeze([1, 2, 3]), (1, 2, 3))
        self.assertEqual(freeze({
                    'list': [1, 2, 3],
                    }),
            frozenset([('list', (1, 2, 3))]))
        self.assertEqual(freeze({
                    'dict': {
                        'inner dict': {
                            'list': [1, 2, 3],
                            'string': 'test',
                            },
                        }
                    }),
            frozenset([('dict',
                        frozenset([('inner dict',
                                    frozenset([
                                            ('list', (1, 2, 3)),
                                            ('string', 'test'),
                                            ]))]))]))

    def testUnfreeze(self):
        "Test unfreeze"
        for value, result in [
                (freeze([1, 2, 3]), [1, 2, 3]),
                (freeze({'dict': {
                                'inner dict': {
                                    'list': [1, 2, 3],
                                    'string': 'test',
                                    },
                                },
                            }),
                    {'dict': {
                            'inner dict': {
                                'list': [1, 2, 3],
                                'string': 'test',
                                },
                            },
                        }),
                ]:
            with self.subTest(value=value):
                self.assertEqual(unfreeze(value), result)

    @with_transaction()
    def test_ignored_context_key_global(self):
        "Test global keys are ignored from context"
        with Transaction().set_context(client='foo'):
            cache_ignored_global_context.set('key', 0)

        with Transaction().set_context(client='bar'):
            value = cache_ignored_global_context.get('key')

        self.assertEqual(value, 0)

    @with_transaction()
    def test_ignored_context_key_local(self):
        "Test local keys are ignored from context"
        with Transaction().set_context(ignored='foo'):
            cache_ignored_local_context.set('key', 1)

        with Transaction().set_context(ignored='bar'):
            value = cache_ignored_local_context.get('key')

        self.assertEqual(value, 1)


class MemoryCacheTestCase(unittest.TestCase):
    "Test Cache"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def setUp(self):
        super().setUp()
        clear_timeout = cache_mod._clear_timeout
        cache_mod._clear_timeout = 1
        self.addCleanup(
            setattr, cache_mod, '_clear_timeout', clear_timeout)

    def tearDown(self):
        MemoryCache.drop(DB_NAME)

    def wait_cache_listening(self):
        pass

    def wait_cache_sync(self, after=None):
        pass

    @with_transaction()
    def test_memory_cache_set_get(self):
        "Test MemoryCache set/get"
        cache.set('foo', 'bar')

        self.assertEqual(cache.get('foo'), 'bar')

    @with_transaction()
    def test_memory_cache_mutable(self):
        "Test MemoryCache with mutable value"
        value = ['bar']
        cache.set('foo', value)
        value.remove('bar')

        self.assertEqual(cache.get('foo'), ['bar'])

    @with_transaction()
    def test_memory_cache_drop(self):
        "Test MemoryCache drop"
        cache.set('foo', 'bar')
        MemoryCache.drop(DB_NAME)

        self.assertEqual(cache.get('foo'), None)

    def test_memory_cache_transactions(self):
        "Test MemoryCache with concurrent transactions"
        transaction1 = Transaction().start(DB_NAME, USER)
        self.wait_cache_listening()
        self.addCleanup(transaction1.stop)

        cache.set('foo', 'bar')
        self.assertEqual(cache.get('foo'), 'bar')

        transaction2 = transaction1.new_transaction()
        self.addCleanup(transaction2.stop)

        cache.clear()
        self.assertEqual(cache.get('foo'), None)

        cache.set('foo', 'baz')
        self.assertEqual(cache.get('foo'), 'baz')

        with Transaction().set_current_transaction(transaction1):
            self.assertEqual(cache.get('foo'), 'bar')

        commit_time = dt.datetime.now()
        transaction2.commit()
        self.wait_cache_sync(after=commit_time)
        self.assertEqual(cache.get('foo'), 'baz')

    def test_memory_cache_nested_transactions(self):
        "Test MemoryCache with nested transactions"
        # Create entry in the cache table to trigger 2 updates
        with Transaction().start(DB_NAME, USER):
            cache.clear()
        # Ensure sync is performed on start
        time.sleep(cache_mod._clear_timeout)

        with Transaction().start(DB_NAME, USER) as transaction1:
            cache.clear()
            with transaction1.new_transaction():
                cache.clear()

    def test_memory_cache_sync(self):
        "Test MemoryCache synchronisation"
        with Transaction().start(DB_NAME, USER):
            cache.clear()
        time.sleep(cache_mod._clear_timeout)
        last = cache._clean_last

        with Transaction().start(DB_NAME, USER):
            self.assertGreater(cache._clean_last, last)

    def test_memory_cache_old_transaction(self):
        "Test old transaction does not fill cache"
        transaction1 = Transaction().start(DB_NAME, USER)
        self.wait_cache_listening()
        self.addCleanup(transaction1.stop)

        # Clear cache from new transaction
        transaction2 = transaction1.new_transaction()
        self.addCleanup(transaction2.stop)
        cache.clear()
        commit_time = dt.datetime.now()
        transaction2.commit()
        self.wait_cache_sync(after=commit_time)

        # Set value from old transaction
        Transaction().set_current_transaction(transaction1)
        self.addCleanup(transaction1.stop)
        cache.set('foo', 'baz')

        # New transaction has still empty cache
        transaction3 = transaction1.new_transaction()
        self.addCleanup(transaction3.stop)
        self.assertEqual(cache.get('foo'), None)

    @with_transaction()
    def test_memory_cache_expire(self):
        "Test expired cache"
        cache_expire.set('foo', "bar")
        time.sleep(cache_expire.duration.total_seconds())

        self.assertEqual(cache_expire.get('foo'), None)


@unittest.skipIf(backend.name == 'sqlite', "SQLite has not channel")
class MemoryCacheChannelTestCase(MemoryCacheTestCase):
    "Test Cache with channel"

    def setUp(self):
        super().setUp()
        clear_timeout = cache_mod._clear_timeout
        cache_mod._clear_timeout = 0
        self.addCleanup(
            setattr, cache_mod, '_clear_timeout', clear_timeout)

    def wait_cache_sync(self, after=None):
        if after is None:
            after = dt.datetime.now()
        while MemoryCache._clean_last < after:
            time.sleep(.01)

    def wait_cache_listening(self):
        pid = os.getpid()
        dbname = Transaction().database.name
        listener = MemoryCache._listener.get((pid, dbname))
        while (not getattr(listener, 'listening', False)
                and listener.is_alive()):
            time.sleep(.01)

    @unittest.skip("No cache sync on transaction start with channel")
    def test_memory_cache_sync(self):
        super().test_memory_cache_sync()


class LRUDictTestCase(unittest.TestCase):
    "Test LRUDict"

    def test_setitem(self):
        lru_dict = LRUDict(1)

        lru_dict['foo'] = 'foo'
        self.assertEqual(len(lru_dict), 1)

        lru_dict['bar'] = 'bar'
        self.assertEqual(len(lru_dict), 1)
        self.assertEqual(lru_dict, {'bar': 'bar'})

    def test_update(self):
        lru_dict = LRUDict(1)

        lru_dict['foo'] = 'foo'
        self.assertEqual(len(lru_dict), 1)

        lru_dict.update(bar='bar')
        lru_dict.update(baz='baz')
        self.assertEqual(len(lru_dict), 1)
        self.assertEqual(lru_dict, {'baz': 'baz'})

    def test_setdefault(self):
        lru_dict = LRUDict(1)

        lru_dict['foo'] = 'foo'
        self.assertEqual(len(lru_dict), 1)

        lru_dict.setdefault('bar', 'value')
        self.assertEqual(len(lru_dict), 1)
        self.assertEqual(lru_dict, {'bar': 'value'})

    def test_default_factory(self):
        lru_dict = LRUDict(1, default_factory=list)

        self.assertEqual(lru_dict['foo'], [])

        lru_dict['bar'].append('bar')
        self.assertEqual(lru_dict, {'bar': ['bar']})

    def test_default_factory_with_key(self):
        lru_dict = LRUDict(
            1, default_factory=lambda k: k, default_factory_with_key=True)

        self.assertEqual(lru_dict['foo'], 'foo')


class LRUDictTransactionTestCase(unittest.TestCase):
    "Test LRUDictTransaction"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_init(self):
        "Test init set to transaction counter"
        lru_dict = LRUDictTransaction(48)

        self.assertEqual(lru_dict.counter, Transaction().counter)

    @with_transaction()
    def test_clear(self):
        "Test clear reset counter"
        lru_dict = LRUDictTransaction(48)

        Transaction().counter += 1
        lru_dict.clear()

        self.assertEqual(lru_dict.counter, Transaction().counter)

    @with_transaction()
    def test_refresh(self):
        "Test refresh"
        lru_dict = LRUDictTransaction(48)

        lru_dict['foo'] = 'foo'
        lru_dict.refresh()

        self.assertEqual(lru_dict, {'foo': 'foo'})

        Transaction().counter += 1
        lru_dict.refresh()

        self.assertEqual(lru_dict, {})
        self.assertEqual(lru_dict.counter, Transaction().counter)
