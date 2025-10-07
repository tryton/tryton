# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import json
import logging
import selectors
import threading
from collections import OrderedDict, defaultdict
from copy import deepcopy
from uuid import uuid4
from weakref import WeakKeyDictionary

from sql import Conflict, Table
from sql.aggregate import Max
from sql.functions import CurrentTimestamp, Function

from trytond import backend, config
from trytond.pool import Pool
from trytond.tools import grouped_slice, resolve
from trytond.tools.multiprocessing import local
from trytond.transaction import Transaction

__all__ = ['BaseCache', 'Cache', 'LRUDict', 'LRUDictTransaction']
logger = logging.getLogger(__name__)

REFRESH_POOL_MSG = "refresh pool"


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
    if isinstance(o, tuple):
        return [unfreeze(x) for x in o]
    elif isinstance(o, frozenset):
        return dict((x, unfreeze(y)) for x, y in o)
    else:
        return o


def _get_modules(cursor):
    ir_module = Table('ir_module')
    cursor.execute(*ir_module.select(
            ir_module.name,
            where=ir_module.state.in_(
                ['activated', 'to upgrade', 'to remove'])))
    return {m for m, in cursor}


class _CacheLocal(local):

    def __init__(self):
        self.listeners = {}
        self.listener_lock = threading.Lock()
        self.portable_id = str(uuid4())


class BaseCache(object):
    _instances = {}
    context_ignored_keys = {
        'client', '_request', '_check_access', '_skip_warnings',
        }

    def __init__(
            self, name, duration=None, context=True,
            context_ignored_keys=None):
        assert ((context_ignored_keys is not None and context)
            or (context_ignored_keys is None)), (
                f"context_ignored_keys ({context_ignored_keys}) is not valid"
                f" in regards to context ({context}).")
        self._name = name
        self.size_limit = config.getint(
            'cache', name, default=config.getint('cache', 'default'))
        self.context = context
        self.context_ignored_keys = set()
        if context and context_ignored_keys:
            self.context_ignored_keys.update(context_ignored_keys)
        self.hit = self.miss = 0
        if isinstance(duration, dt.timedelta):
            self.duration = duration
        elif isinstance(duration, (int, float)):
            self.duration = dt.timedelta(seconds=duration)
        elif duration:
            self.duration = dt.timedelta(**duration)
        else:
            self.duration = None
        assert self._name not in self._instances, self._name
        self._instances[self._name] = self

    @classmethod
    def stats(cls):
        for name, inst in cls._instances.items():
            yield {
                'name': name,
                'hit': inst.hit,
                'miss': inst.miss,
                }

    def _key(self, key):
        if self.context:
            context = Transaction().context.copy()
            for k in (self.__class__.context_ignored_keys
                    | self.context_ignored_keys):
                context.pop(k, None)
            return (key, freeze(context))
        return key

    def get(self, key, default=None):
        raise NotImplementedError

    def set(self, key, value):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

    @classmethod
    def clear_all(cls):
        for inst in cls._instances.values():
            inst.clear()

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
    _clean_last = None
    _default_lower = Transaction.monotonic_time()
    _local = _CacheLocal()
    _table = 'ir_cache'
    _channel = _table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._database_cache = defaultdict(lambda: LRUDict(self.size_limit))
        self._transaction_cache = WeakKeyDictionary()
        self._transaction_lower = {}
        self._timestamp = {}

    def _get_cache(self):
        transaction = Transaction()
        dbname = transaction.database.name
        lower = self._transaction_lower.get(dbname, self._default_lower)
        if (self._name in self._reset.get(transaction, set())
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
            expire, result = cache[key]
            if expire and expire < dt.datetime.now():
                del cache[key]
                self.miss += 1
                return default
            cache.move_to_end(key)
            self.hit += 1
            return deepcopy(result)
        except (KeyError, TypeError):
            self.miss += 1
            return default

    def set(self, key, value):
        key = self._key(key)
        cache = self._get_cache()
        if self.duration:
            expire = dt.datetime.now() + self.duration
        else:
            expire = None
        try:
            cache[key] = (expire, deepcopy(value))
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
    def _clear_all(cls, dbname):
        for inst in cls._instances.values():
            inst._clear(dbname)

    @classmethod
    def sync(cls, transaction):
        if cls._clean_last is None:
            cls._clean_last = dt.datetime.now()
            return

        database = transaction.database
        dbname = database.name
        clean_timeout = config.getint('cache', 'clean_timeout')
        if not clean_timeout and database.has_channel():
            with cls._local.listener_lock:
                if dbname not in cls._local.listeners:
                    listener = threading.Thread(
                        target=cls._listen, args=(dbname,), daemon=True)
                    cls._local.listeners[dbname] = listener
                    listener.start()
            return
        last_clean = (dt.datetime.now() - cls._clean_last).total_seconds()
        if last_clean < clean_timeout:
            return
        connection = database.get_connection(readonly=True, autocommit=True)
        try:
            with connection.cursor() as cursor:
                table = Table(cls._table)
                cursor.execute(*table.select(
                        _cast(table.timestamp), table.name))
                timestamps = {}
                for timestamp, name in cursor:
                    timestamps[name] = timestamp
                modules = _get_modules(cursor)
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
        Pool.refresh(dbname, modules)
        cls._clean_last = dt.datetime.now()

    def sync_since(self, value):
        return self._clean_last > value

    @classmethod
    def commit(cls, transaction):
        table = Table(cls._table)
        reset = cls._reset.pop(transaction, None)
        if not reset:
            return
        database = transaction.database
        dbname = database.name
        clean_timeout = config.getint('cache', 'clean_timeout')
        if not clean_timeout and transaction.database.has_channel():
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
                        if database.has_insert_on_conflict():
                            query = table.insert(
                                [table.timestamp, table.name],
                                [[CurrentTimestamp(), name]],
                                on_conflict=Conflict(
                                    table,
                                    indexed_columns=[table.name],
                                    columns=[table.timestamp],
                                    values=[CurrentTimestamp()]))
                            if database.has_returning():
                                query.returning = [table.timestamp]
                            cursor.execute(*query)
                        else:
                            cursor.execute(*table.select(table.name, table.id,
                                    table.timestamp,
                                    where=table.name == name,
                                    limit=1))
                            if cursor.fetchone():
                                query = table.update(
                                    [table.timestamp],
                                    [CurrentTimestamp()],
                                    where=table.name == name)
                            else:
                                query = table.insert(
                                    [table.timestamp, table.name],
                                    [[CurrentTimestamp(), name]])
                            if database.has_returning():
                                query.returning = [table.timestamp]
                            cursor.execute(*query)
                        if not database.has_returning():
                            cursor.execute(*table.select(
                                    Max(table.timestamp),
                                    where=table.name == name))
                        timestamp, = cursor.fetchone()
                        try:
                            inst = cls._instances[name]
                        except KeyError:
                            pass
                        else:
                            inst._clear(dbname, timestamp)
                connection.commit()
            finally:
                database.put_connection(connection)
            cls._clean_last = dt.datetime.now()
        reset.clear()

    @classmethod
    def rollback(cls, transaction):
        cls._reset.pop(transaction, None)

    @classmethod
    def drop(cls, dbname):
        with cls._local.listener_lock:
            listener = cls._local.listeners.pop(dbname, None)
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
    def refresh_pool(cls, transaction):
        database = transaction.database
        dbname = database.name
        clean_timeout = config.getint('cache', 'clean_timeout')
        if not clean_timeout and database.has_channel():
            database = backend.Database(dbname)
            conn = database.get_connection()
            process_id = cls._local.portable_id
            payload = f"{REFRESH_POOL_MSG} {process_id}"
            try:
                cursor = conn.cursor()
                cursor.execute(f'NOTIFY "{cls._channel}", %s', (payload,))
                conn.commit()
            finally:
                database.put_connection(conn)

    @classmethod
    def _listen(cls, dbname):
        current_thread = threading.current_thread()

        conn, selector = None, None
        try:
            database = backend.Database(dbname)
            if not database.has_channel():
                raise NotImplementedError

            logger.info(
                "listening on channel '%s' of '%s'", cls._channel, dbname)
            conn = database.get_connection(autocommit=True)
            selector = selectors.DefaultSelector()

            cursor = conn.cursor()
            cursor.execute('LISTEN "%s"' % cls._channel)
            # Clear everything in case we missed a payload
            Pool.refresh(dbname, _get_modules(cursor))
            cls._clear_all(dbname)
            current_thread.listening = True

            selector.register(conn, selectors.EVENT_READ)
            while cls._local.listeners.get(dbname) == current_thread:
                selector.select(
                    timeout=config.getint('cache', 'select_timeout'))
                conn.poll()
                while conn.notifies:
                    notification = conn.notifies.pop()
                    payload = notification.payload
                    if payload and payload.startswith(REFRESH_POOL_MSG):
                        remote_id = payload[len(REFRESH_POOL_MSG) + 1:]
                        process_id = cls._local.portable_id
                        if remote_id != process_id:
                            Pool.refresh(dbname, _get_modules(cursor))
                    elif payload:
                        for name in json.loads(payload):
                            try:
                                inst = cls._instances[name]
                            except KeyError:
                                pass
                            else:
                                inst._clear(dbname)
                cls._clean_last = dt.datetime.now()
                # Keep connected
                cursor.execute('SELECT 1')
        except Exception:
            logger.error(
                "cache listener on '%s' crashed", dbname, exc_info=True)
            raise
        finally:
            if selector:
                selector.close()
            if conn:
                database.put_connection(conn)
            with cls._local.listener_lock:
                if cls._local.listeners.get(dbname) == current_thread:
                    del cls._local.listeners[dbname]


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
    If default_factory_with_key is set, the default_factory is called with the
    missing key.
    """
    __slots__ = ('size_limit',)

    def __init__(self, size_limit,
            default_factory=None, default_factory_with_key=False,
            *args, **kwargs):
        assert size_limit > 0
        self.size_limit = size_limit
        super().__init__(*args, **kwargs)
        self.default_factory = default_factory
        self.default_factory_with_key = default_factory_with_key
        self._check_size_limit()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._check_size_limit()

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        if self.default_factory_with_key:
            value = self.default_factory(key)
        else:
            value = self.default_factory()
        self[key] = value
        return value

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._check_size_limit()

    def setdefault(self, key, default=None):
        default = super().setdefault(key, default=default)
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
        super().__init__(*args, **kwargs)
        self.transaction = Transaction()
        self.counter = self.transaction.counter

    def clear(self):
        super().clear()
        self.counter = self.transaction.counter

    def refresh(self):
        if self.counter != self.transaction.counter:
            self.clear()
