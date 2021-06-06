# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import json
import logging
import os
import select
import threading
from collections import OrderedDict, defaultdict
from datetime import datetime
from weakref import WeakKeyDictionary

from sql import Table
from sql.aggregate import Max
from sql.functions import CurrentTimestamp, Function

from trytond import backend
from trytond.config import config
from trytond.transaction import Transaction
from trytond.tools import resolve, grouped_slice

__all__ = ['BaseCache', 'Cache', 'LRUDict', 'LRUDictTransaction']
_clear_timeout = config.getint('cache', 'clean_timeout', default=5 * 60)
logger = logging.getLogger(__name__)


def _cast(column):
    class SQLite_DateTime(Function):
        __slots__ = ()
        _function = 'DATETIME'

    if backend.name == 'sqlite':
        column = SQLite_DateTime(column)
    return column


def freeze(o):
    if isinstance(o, (set, tuple, list)):
        return tuple(freeze(x) for x in o)
    elif isinstance(o, dict):
        return frozenset((x, freeze(y)) for x, y in o.items())
    else:
        return o


def unfreeze(o):
    if isinstance(o, frozenset):
        return dict((x, unfreeze(y)) for x, y in o)
    else:
        return o


class BaseCache(object):
    _instances = {}

    def __init__(self, name, size_limit=1024, duration=None, context=True):
        self._name = name
        self.size_limit = size_limit
        self.context = context
        if isinstance(duration, dt.timedelta):
            self.duration = duration
        elif isinstance(duration, (int, float)):
            self.duration = dt.timedelta(seconds=duration)
        elif duration:
            self.duration = dt.timedelta(**duration)
        else:
            self.duration = None
        assert self._name not in self._instances
        self._instances[self._name] = self

    def _key(self, key):
        if self.context:
            context = Transaction().context.copy()
            context.pop('client', None)
            context.pop('_request', None)
            return (key, Transaction().user, freeze(context))
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

    def sync_since(self, value):
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
    _default_lower = Transaction.monotonic_time()
    _listener = {}
    _listener_lock = defaultdict(threading.Lock)
    _table = 'ir_cache'
    _channel = _table

    def __init__(self, *args, **kwargs):
        super(MemoryCache, self).__init__(*args, **kwargs)
        self._database_cache = defaultdict(lambda: LRUDict(self.size_limit))
        self._transaction_cache = WeakKeyDictionary()
        self._transaction_lower = {}
        self._timestamp = {}

    def _get_cache(self):
        transaction = Transaction()
        dbname = transaction.database.name
        lower = self._transaction_lower.get(dbname, self._default_lower)
        if (transaction in self._reset
                or transaction.started_at < lower):
            try:
                return self._transaction_cache[transaction]
            except KeyError:
                cache = self._database_cache.default_factory()
                self._transaction_cache[transaction] = cache
                return cache
        else:
            return self._database_cache[dbname]

    def get(self, key, default=None):
        key = self._key(key)
        cache = self._get_cache()
        try:
            (expire, result) = cache.pop(key)
            if expire and expire < dt.datetime.now():
                return default
            cache[key] = (expire, result)
            return result
        except (KeyError, TypeError):
            return default

    def set(self, key, value):
        key = self._key(key)
        cache = self._get_cache()
        if self.duration:
            expire = dt.datetime.now() + self.duration
        else:
            expire = None
        try:
            cache[key] = (expire, value)
        except TypeError:
            pass
        return value

    def clear(self):
        transaction = Transaction()
        self._reset.setdefault(transaction, set()).add(self._name)
        self._transaction_cache.pop(transaction, None)

    def _clear(self, dbname, timestamp=None):
        logger.debug("clearing cache '%s' of '%s'", self._name, dbname)
        self._timestamp[dbname] = timestamp
        self._database_cache[dbname] = self._database_cache.default_factory()
        self._transaction_lower[dbname] = max(
            Transaction.monotonic_time(),
            self._transaction_lower.get(dbname, self._default_lower))

    @classmethod
    def sync(cls, transaction):
        database = transaction.database
        dbname = database.name
        if not _clear_timeout and database.has_channel():
            pid = os.getpid()
            with cls._listener_lock[pid]:
                if (pid, dbname) not in cls._listener:
                    cls._listener[pid, dbname] = listener = threading.Thread(
                        target=cls._listen, args=(dbname,), daemon=True)
                    listener.start()
            return
        if (datetime.now() - cls._clean_last).total_seconds() < _clear_timeout:
            return
        connection = database.get_connection(readonly=True, autocommit=True)
        try:
            with connection.cursor() as cursor:
                table = Table(cls._table)
                cursor.execute(*table.select(
                        _cast(table.timestamp), table.name))
                timestamps = {}
                for timestamp, name in cursor.fetchall():
                    timestamps[name] = timestamp
        finally:
            database.put_connection(connection)
        for name, timestamp in timestamps.items():
            try:
                inst = cls._instances[name]
            except KeyError:
                continue
            inst_timestamp = inst._timestamp.get(dbname)
            if not inst_timestamp or timestamp > inst_timestamp:
                inst._clear(dbname, timestamp)
        cls._clean_last = datetime.now()

    def sync_since(self, value):
        return self._clean_last > value

    @classmethod
    def commit(cls, transaction):
        table = Table(cls._table)
        reset = cls._reset.setdefault(transaction, set())
        if not reset:
            return
        database = transaction.database
        dbname = database.name
        if not _clear_timeout and transaction.database.has_channel():
            with transaction.connection.cursor() as cursor:
                # The count computed as
                # 8000 (max notify size) / 64 (max name data len)
                for sub_reset in grouped_slice(reset, 125):
                    cursor.execute(
                        'NOTIFY "%s", %%s' % cls._channel,
                        (json.dumps(list(sub_reset), separators=(',', ':')),))
        else:
            connection = database.get_connection(
                readonly=False, autocommit=True)
            try:
                with connection.cursor() as cursor:
                    for name in reset:
                        cursor.execute(*table.select(table.name, table.id,
                                table.timestamp,
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

                        cursor.execute(*table.select(
                                _cast(Max(table.timestamp)),
                                where=table.name == name))
                        timestamp, = cursor.fetchone()

                        inst = cls._instances[name]
                        inst._clear(dbname, timestamp)
                connection.commit()
            finally:
                database.put_connection(connection)
            cls._clean_last = datetime.now()
        reset.clear()

    @classmethod
    def rollback(cls, transaction):
        try:
            cls._reset[transaction].clear()
        except KeyError:
            pass

    @classmethod
    def drop(cls, dbname):
        pid = os.getpid()
        with cls._listener_lock[pid]:
            listener = cls._listener.pop((pid, dbname), None)
        if listener:
            database = backend.Database(dbname)
            conn = database.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('NOTIFY "%s"' % cls._channel)
                conn.commit()
            finally:
                database.put_connection(conn)
            listener.join()
        for inst in cls._instances.values():
            inst._timestamp.pop(dbname, None)
            inst._database_cache.pop(dbname, None)
            inst._transaction_lower.pop(dbname, None)

    @classmethod
    def _listen(cls, dbname):
        database = backend.Database(dbname)
        if not database.has_channel():
            raise NotImplementedError

        logger.info("listening on channel '%s' of '%s'", cls._channel, dbname)
        conn = database.get_connection(autocommit=True)
        pid = os.getpid()
        current_thread = threading.current_thread()
        try:
            cursor = conn.cursor()
            cursor.execute('LISTEN "%s"' % cls._channel)

            while cls._listener.get((pid, dbname)) == current_thread:
                readable, _, _ = select.select([conn], [], [])
                if not readable:
                    continue

                conn.poll()
                while conn.notifies:
                    notification = conn.notifies.pop()
                    if notification.payload:
                        reset = json.loads(notification.payload)
                        for name in reset:
                            inst = cls._instances[name]
                            inst._clear(dbname)
                cls._clean_last = datetime.now()
        except Exception:
            logger.error(
                "cache listener on '%s' crashed", dbname, exc_info=True)
            raise
        finally:
            database.put_connection(conn)
            with cls._listener_lock[pid]:
                if cls._listener.get((pid, dbname)) == current_thread:
                    del cls._listener[pid, dbname]


if config.get('cache', 'class'):
    Cache = resolve(config.get('cache', 'class'))
else:
    Cache = MemoryCache


class LRUDict(OrderedDict):
    """
    Dictionary with a size limit.
    If size limit is reached, it will remove the first added items.
    The default_factory provides the same behavior as in standard
    collections.defaultdict.
    """
    __slots__ = ('size_limit',)

    def __init__(self, size_limit, default_factory=None, *args, **kwargs):
        assert size_limit > 0
        self.size_limit = size_limit
        super(LRUDict, self).__init__(*args, **kwargs)
        self.default_factory = default_factory
        self._check_size_limit()

    def __setitem__(self, key, value):
        super(LRUDict, self).__setitem__(key, value)
        self._check_size_limit()

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

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
    Dictionary with a size limit and default_factory. (see LRUDict)
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
