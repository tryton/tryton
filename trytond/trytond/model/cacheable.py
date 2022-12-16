#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.tools import Cache
from threading import Lock
import time


class Cacheable(object):
    _name = None

    def __init__(self):
        super(Cacheable, self).__init__()
        self._cache = {}
        self._max_len = 1024
        self._timeout = 3600
        self._lock = Lock()
        self._timestamp = None
        Cache._cache_instance.append(self)

    def add(self, cursor, key, value):
        self._lock.acquire()
        try:
            self._cache.setdefault(cursor.dbname, {})

            lower = None
            if len(self._cache[cursor.dbname]) > self._max_len:
                mintime = time.time() - self._timeout
                for key2 in self._cache[cursor.dbname].keys():
                    last_time = self._cache[cursor.dbname][key2][1]
                    if mintime > last_time:
                        del self._cache[cursor.dbname][key2]
                    else:
                        if not lower or lower[1] > last_time:
                            lower = (key2, last_time)
            if len(self._cache[cursor.dbname]) > self._max_len and lower:
                del self._cache[cursor.dbname][lower[0]]

            self._cache[cursor.dbname][key] = (value, time.time())
        finally:
            self._lock.release()

    def invalidate(self, cursor, key):
        self._lock.acquire()
        try:
            del self._cache[cursor.dbname][key]
        finally:
            self._lock.release()

    def get(self, cursor, key):
        try:
            return self._cache[cursor.dbname][key][0]
        except KeyError:
            return None

    def clear(self, cursor):
        self._lock.acquire()
        try:
            self._cache.setdefault(cursor.dbname, {})
            self._cache[cursor.dbname].clear()
            Cache.reset(cursor.dbname, self._name)
        finally:
            self._lock.release()
