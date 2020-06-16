# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import time
import unittest

from trytond import backend, cache as cache_mod
from trytond.cache import freeze, MemoryCache
from trytond.tests.test_tryton import with_transaction, activate_module
from trytond.tests.test_tryton import DB_NAME, USER
from trytond.transaction import Transaction


cache = MemoryCache('test.cache')
cache_expire = MemoryCache('test.cache_expire', duration=1)


class CacheTestCase(unittest.TestCase):
    "Test Cache"

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

    def wait_cache_sync(self):
        pass

    @with_transaction()
    def test_memory_cache_set_get(self):
        "Test MemoryCache set/get"
        cache.set('foo', 'bar')

        self.assertEqual(cache.get('foo'), 'bar')

    @with_transaction()
    def test_memory_cache_drop(self):
        "Test MemoryCache drop"
        cache.set('foo', 'bar')
        MemoryCache.drop(DB_NAME)

        self.assertEqual(cache.get('foo'), None)

    def test_memory_cache_transactions(self):
        "Test MemoryCache with concurrent transactions"
        transaction1 = Transaction().start(DB_NAME, USER)
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

        transaction2.commit()
        for n in range(10):
            if cache.get('foo') == 'baz':
                break
            self.wait_cache_sync()
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
        self.addCleanup(transaction1.stop)

        # Clear cache from new transaction
        transaction2 = transaction1.new_transaction()
        self.addCleanup(transaction2.stop)
        cache.clear()
        transaction2.commit()
        self.wait_cache_sync()

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

    def wait_cache_sync(self):
        time.sleep(1)

    @unittest.skip("No cache sync on transaction start with channel")
    def test_memory_cache_sync(self):
        super().test_memory_cache_sync()


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in [
            CacheTestCase,
            MemoryCacheTestCase,
            MemoryCacheChannelTestCase]:
        suite.addTests(func(testcase))
    return suite
