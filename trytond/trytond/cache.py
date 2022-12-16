# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from threading import Lock
from collections import OrderedDict

from sql import Table
from sql.functions import Now

from trytond.transaction import Transaction

__all__ = ['Cache', 'LRUDict']


def freeze(o):
    if isinstance(o, (set, tuple, list)):
        return tuple(freeze(x) for x in o)
    elif isinstance(o, dict):
        return frozenset((x, freeze(y)) for x, y in o.iteritems())
    else:
        return o


class Cache(object):
    """
    A key value LRU cache with size limit.
    """
    _cache_instance = []
    _resets = {}
    _resets_lock = Lock()

    def __init__(self, name, size_limit=1024, context=True):
        self.size_limit = size_limit
        self.context = context
        self._cache = {}
        self._cache_instance.append(self)
        self._name = name
        self._timestamp = None
        self._lock = Lock()

    def _key(self, key):
        if self.context:
            return (key, Transaction().user, freeze(Transaction().context))
        return key

    def get(self, key, default=None):
        cursor = Transaction().cursor
        key = self._key(key)
        with self._lock:
            cache = self._cache.setdefault(cursor.dbname,
                LRUDict(self.size_limit))
            try:
                result = cache[key] = cache.pop(key)
                return result
            except (KeyError, TypeError):
                return default

    def set(self, key, value):
        cursor = Transaction().cursor
        key = self._key(key)
        with self._lock:
            cache = self._cache.setdefault(cursor.dbname,
                LRUDict(self.size_limit))
            try:
                cache[key] = value
            except TypeError:
                pass
        return value

    def clear(self):
        cursor = Transaction().cursor
        Cache.reset(cursor.dbname, self._name)
        with self._lock:
            self._cache[cursor.dbname] = LRUDict(self.size_limit)

    @staticmethod
    def clean(dbname):
        with Transaction().new_cursor():
            cursor = Transaction().cursor
            table = Table('ir_cache')
            cursor.execute(*table.select(table.timestamp, table.name))
            timestamps = {}
            for timestamp, name in cursor.fetchall():
                timestamps[name] = timestamp
        for inst in Cache._cache_instance:
            if inst._name in timestamps:
                with inst._lock:
                    if (not inst._timestamp
                            or timestamps[inst._name] > inst._timestamp):
                        inst._timestamp = timestamps[inst._name]
                        inst._cache[dbname] = LRUDict(inst.size_limit)

    @staticmethod
    def reset(dbname, name):
        with Cache._resets_lock:
            Cache._resets.setdefault(dbname, set())
            Cache._resets[dbname].add(name)

    @staticmethod
    def resets(dbname):
        with Transaction().new_cursor():
            cursor = Transaction().cursor
            table = Table('ir_cache')
            with Cache._resets_lock:
                Cache._resets.setdefault(dbname, set())
                for name in Cache._resets[dbname]:
                    cursor.execute(*table.select(table.name,
                            where=table.name == name))
                    if cursor.fetchone():
                        # It would be better to insert only
                        cursor.execute(*table.update([table.timestamp],
                                [Now()], where=table.name == name))
                    else:
                        cursor.execute(*table.insert(
                                [table.timestamp, table.name],
                                [[Now(), name]]))
                Cache._resets[dbname].clear()
            cursor.commit()

    @classmethod
    def drop(cls, dbname):
        for inst in cls._cache_instance:
            inst._cache.pop(dbname, None)


class LRUDict(OrderedDict):
    """
    Dictionary with a size limit.
    If size limit is reached, it will remove the first added items.
    """
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
