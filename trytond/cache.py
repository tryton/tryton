# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import OrderedDict, defaultdict
from datetime import datetime
from weakref import WeakKeyDictionary

from sql import Table
from sql.aggregate import Max
from sql.functions import CurrentTimestamp

from trytond.config import config
from trytond.transaction import Transaction
from trytond.tools import resolve

__all__ = ['BaseCache', 'Cache', 'LRUDict']
_clear_timeout = config.getint('cache', 'clean_timeout', default=5 * 60)


def freeze(o):
    if isinstance(o, (set, tuple, list)):
        return tuple(freeze(x) for x in o)
    elif isinstance(o, dict):
        return frozenset((x, freeze(y)) for x, y in o.items())
    else:
        return o


class BaseCache(object):
    _instances = {}

    def __init__(self, name, size_limit=1024, context=True):
        self._name = name
        self.size_limit = size_limit
        self.context = context
        assert self._name not in self._instances
        self._instances[self._name] = self

    def _key(self, key):
        if self.context:
            return (key, Transaction().user, freeze(Transaction().context))
        return key

    def get(self, key, default=None):
        raise NotImplementedError

    def set(self, key, value):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    @classmethod
    def sync(cls, transaction):
        raise NotImplementedError

    @classmethod
    def commit(cls, transaction):
        raise NotImplementedError

    @classmethod
    def rollback(cls, transaction):
        raise NotImplementedError

    @classmethod
    def drop(cls, dbname):
        raise NotImplementedError


class MemoryCache(BaseCache):
    """
    A key value LRU cache with size limit.
    """
    _reset = WeakKeyDictionary()
    _clean_last = datetime.now()

    def __init__(self, name, size_limit=1024, context=True):
        super(MemoryCache, self).__init__(name, size_limit, context)
        self._database_cache = defaultdict(lambda: LRUDict(size_limit))
        self._transaction_cache = WeakKeyDictionary()
        self._timestamp = None

    def _get_cache(self):
        transaction = Transaction()
        dbname = transaction.database.name
        if transaction in self._reset:
            try:
                return self._transaction_cache[transaction]
            except KeyError:
                self._transaction_cache[transaction] = LRUDict(self.size_limit)
                return self._transaction_cache[transaction]
        else:
            return self._database_cache[dbname]

    def get(self, key, default=None):
        key = self._key(key)
        cache = self._get_cache()
        try:
            result = cache[key] = cache.pop(key)
            return result
        except (KeyError, TypeError):
            return default

    def set(self, key, value):
        key = self._key(key)
        cache = self._get_cache()
        try:
            cache[key] = value
        except TypeError:
            pass
        return value

    def clear(self):
        transaction = Transaction()
        self._reset.setdefault(transaction, set()).add(self._name)
        self._transaction_cache.pop(transaction, None)

    @classmethod
    def sync(cls, transaction):
        if (datetime.now() - cls._clean_last).total_seconds() < _clear_timeout:
            return
        dbname = transaction.database.name
        with transaction.connection.cursor() as cursor:
            table = Table('ir_cache')
            cursor.execute(*table.select(table.timestamp, table.name))
            timestamps = {}
            for timestamp, name in cursor.fetchall():
                timestamps[name] = timestamp
        for name, timestamp in timestamps.items():
            try:
                inst = cls._instances[name]
            except KeyError:
                continue
            if not inst._timestamp or timestamp > inst._timestamp:
                inst._timestamp = timestamp
                inst._database_cache[dbname] = LRUDict(inst.size_limit)
        cls._clean_last = datetime.now()

    @classmethod
    def commit(cls, transaction):
        table = Table('ir_cache')
        reset = cls._reset.setdefault(transaction, set())
        if not reset:
            return
        dbname = transaction.database.name
        with transaction.connection.cursor() as cursor:
            for name in reset:
                cursor.execute(*table.select(table.name,
                        where=table.name == name,
                        limit=1))
                if cursor.fetchone():
                    # It would be better to insert only
                    cursor.execute(*table.update([table.timestamp],
                            [CurrentTimestamp()],
                            where=table.name == name))
                else:
                    cursor.execute(*table.insert(
                            [table.timestamp, table.name],
                            [[CurrentTimestamp(), name]]))

                cursor.execute(*table.select(
                        Max(table.timestamp),
                        where=table.name == name))
                timestamp, = cursor.fetchone()

                inst = cls._instances[name]
                inst._timestamp = timestamp
                inst._database_cache[dbname] = LRUDict(inst.size_limit)

    @classmethod
    def rollback(cls, transaction):
        try:
            cls._reset[transaction].clear()
        except KeyError:
            pass

    @classmethod
    def drop(cls, dbname):
        for inst in cls._instances.values():
            inst._database_cache.pop(dbname, None)


if config.get('cache', 'class'):
    Cache = resolve(config.get('cache', 'class'))
else:
    Cache = MemoryCache


class LRUDict(OrderedDict):
    """
    Dictionary with a size limit.
    If size limit is reached, it will remove the first added items.
    """
    __slots__ = ('size_limit',)

    def __init__(self, size_limit, *args, **kwargs):
        assert size_limit > 0
        self.size_limit = size_limit
        super(LRUDict, self).__init__(*args, **kwargs)
        self._check_size_limit()

    def __setitem__(self, key, value):
        super(LRUDict, self).__setitem__(key, value)
        self._check_size_limit()

    def update(self, *args, **kwargs):
        super(LRUDict, self).update(*args, **kwargs)
        self._check_size_limit()

    def setdefault(self, key, default=None):
        default = super(LRUDict, self).setdefault(key, default=default)
        self._check_size_limit()
        return default

    def _check_size_limit(self):
        while len(self) > self.size_limit:
            self.popitem(last=False)


class LRUDictTransaction(LRUDict):
    """
    Dictionary with a size limit. (see LRUDict)
    It is refreshed when transaction counter is changed.
    """
    __slots__ = ('transaction', 'counter')

    def __init__(self, *args, **kwargs):
        super(LRUDictTransaction, self).__init__(*args, **kwargs)
        self.transaction = Transaction()
        self.counter = self.transaction.counter

    def clear(self):
        super(LRUDictTransaction, self).clear()
        self.counter = self.transaction.counter

    def refresh(self):
        if self.counter != self.transaction.counter:
            self.clear()
