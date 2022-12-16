#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import inspect
import time
import datetime
from threading import Lock
from trytond.transaction import Transaction
from trytond.config import CONFIG
from trytond.backend import Database
from trytond.tools import OrderedDict


class Cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """
    _cache_instance = []
    _resets = {}
    _resets_lock = Lock()

    def __init__(self, name, timeout=3600, max_len=1024):
        self.timeout = timeout
        self.max_len = max_len
        self._cache = {}
        self._cache_instance.append(self)
        self._name = name
        self._timestamp = None
        self._lock = Lock()

    def __call__(self, function):
        arg_names = inspect.getargspec(function)[0]

        def reset():
            dbname = Transaction().cursor.dbname
            Cache.reset(dbname, self._name)
            self._lock.acquire()
            try:
                self._cache[dbname] = {}
            finally:
                self._lock.release()
            return True

        def call(model, *args, **kwargs):
            result = None
            find = False
            cursor = Transaction().cursor
            # Update named arguments with positional argument values
            kwargs_origin = kwargs.copy()
            kwargs.update(dict(zip(arg_names, args)))
            kwargs = kwargs.items()
            kwargs.sort()

            self._lock.acquire()
            try:
                self._cache.setdefault(cursor.dbname, {})
            finally:
                self._lock.release()

            lower = None
            self._lock.acquire()
            try:
                if len(self._cache[cursor.dbname]) > self.max_len:
                    mintime = time.time() - self.timeout
                    for key in self._cache[cursor.dbname].keys():
                        last_time = self._cache[cursor.dbname][key][1]
                        if mintime > last_time:
                            del self._cache[cursor.dbname][key]
                        else:
                            if not lower or lower[1] > last_time:
                                lower = (key, last_time)
                if (len(self._cache[cursor.dbname]) > self.max_len
                        and lower):
                    del self._cache[cursor.dbname][lower[0]]
            finally:
                self._lock.release()

            # Work out key as a tuple
            key = (id(model), Transaction().user, repr(Transaction().context),
                    repr(kwargs))

            # Check cache and return cached value if possible
            self._lock.acquire()
            try:
                if key in self._cache[cursor.dbname]:
                    (value, last_time) = self._cache[cursor.dbname][key]
                    mintime = time.time() - self.timeout
                    if self.timeout <= 0 or mintime <= last_time:
                        self._cache[cursor.dbname][key] = (value,
                                time.time())
                        result = value
                        find = True
            finally:
                self._lock.release()

            if not find:
                # Work out new value, cache it and return it
                result = function(model, *args, **kwargs_origin)

                self._lock.acquire()
                try:
                    self._cache[cursor.dbname][key] = (result, time.time())
                finally:
                    self._lock.release()
            return result

        call.__doc__ = function.__doc__
        call.reset = reset
        return call

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
        for obj in Cache._cache_instance:
            if obj._name in timestamps:
                if not obj._timestamp or timestamps[obj._name] > obj._timestamp:
                    obj._timestamp = timestamps[obj._name]
                    obj._lock.acquire()
                    try:
                        obj._cache[dbname] = {}
                    finally:
                        obj._lock.release()

    @staticmethod
    def reset(dbname, name):
        if not CONFIG['multi_server']:
            return
        Cache._resets_lock.acquire()
        try:
            Cache._resets.setdefault(dbname, set())
            Cache._resets[dbname].add(name)
        finally:
            Cache._resets_lock.release()
        return

    @staticmethod
    def resets(dbname):
        if not CONFIG['multi_server']:
            return
        database = Database(dbname).connect()
        cursor = database.cursor()
        Cache._resets_lock.acquire()
        Cache._resets.setdefault(dbname, set())
        try:
            for name in Cache._resets[dbname]:
                cursor.execute('SELECT name FROM ir_cache WHERE name = %s',
                            (name,))
                if cursor.fetchone():
                    cursor.execute('UPDATE ir_cache SET "timestamp" = %s '\
                            'WHERE name = %s', (datetime.datetime.now(), name))
                else:
                    cursor.execute('INSERT INTO ir_cache ' \
                            '("timestamp", "name") ' \
                            'VALUES (%s, %s)', (datetime.datetime.now(), name))
            Cache._resets[dbname].clear()
        finally:
            cursor.commit()
            cursor.close()
            Cache._resets_lock.release()


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
