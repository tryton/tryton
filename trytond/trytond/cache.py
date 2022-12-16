#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from threading import Lock
from trytond.transaction import Transaction
from trytond.config import CONFIG
from trytond.backend import Database
from trytond.tools import OrderedDict

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

    def clear(self):
        cursor = Transaction().cursor
        Cache.reset(cursor.dbname, self._name)
        with self._lock:
            self._cache[cursor.dbname] = LRUDict(self.size_limit)

    @staticmethod
    def clean(dbname):
        if not CONFIG['multi_server']:
            return
        database = Database(dbname).connect()
        cursor = database.cursor()
        try:
            cursor.execute('SELECT "timestamp", "name" FROM ir_cache')
            timestamps = {}
            for timestamp, name in cursor.fetchall():
                timestamps[name] = timestamp
        finally:
            cursor.commit()
            cursor.close()
        for inst in Cache._cache_instance:
            if inst._name in timestamps:
                with inst._lock:
                    if (not inst._timestamp
                            or timestamps[inst._name] > inst._timestamp):
                        inst._timestamp = timestamps[inst._name]
                        inst._cache[dbname] = LRUDict(inst.size_limit)

    @staticmethod
    def reset(dbname, name):
        if not CONFIG['multi_server']:
            return
        with Cache._resets_lock:
            Cache._resets.setdefault(dbname, set())
            Cache._resets[dbname].add(name)

    @staticmethod
    def resets(dbname):
        if not CONFIG['multi_server']:
            return
        database = Database(dbname).connect()
        cursor = database.cursor()
        try:
            with Cache._resets_lock:
                Cache._resets.setdefault(dbname, set())
                for name in Cache._resets[dbname]:
                    cursor.execute('SELECT name FROM ir_cache WHERE name = %s',
                        (name,))
                    if cursor.fetchone():
                        # It would be better to insert only
                        cursor.execute('UPDATE ir_cache SET "timestamp" = %s '
                            'WHERE name = %s', (datetime.datetime.now(), name))
                    else:
                        cursor.execute('INSERT INTO ir_cache '
                            '("timestamp", "name") '
                            'VALUES (%s, %s)', (datetime.datetime.now(), name))
                Cache._resets[dbname].clear()
        finally:
            cursor.commit()
            cursor.close()


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
