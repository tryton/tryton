# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import time
from collections import defaultdict, deque
from functools import wraps
from threading import local
from weakref import WeakValueDictionary

from sql import Flavor

from trytond.config import config
from trytond.tools.immutabledict import ImmutableDict

__all__ = ['Transaction',
    'check_access', 'without_check_access',
    'active_records', 'inactive_records']

_retry = config.getint('database', 'retry')
_cache_transaction = config.getint('cache', 'transaction')
_cache_model = config.getint('cache', 'model')
_cache_record = config.getint('cache', 'record')
logger = logging.getLogger(__name__)


class TransactionError(Exception):
    def fix(self, extras):
        pass


class _TransactionLockError(TransactionError):
    def __init__(self, table):
        super().__init__()
        self._table = table

    def fix(self, extras):
        super().fix(extras)
        extras.setdefault('_lock_tables', []).append(self._table)


def record_cache_size(transaction):
    return transaction.context.get('_record_cache_size', _cache_record)


def check_access(func=None, *, _access=True):
    if func:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with check_access(_access=_access):
                return func(*args, **kwargs)
        return wrapper
    else:
        return Transaction().set_context(_check_access=_access)


def without_check_access(func=None):
    return check_access(func=func, _access=False)


def active_records(func=None, *, _test=True):
    if func:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with active_records(_test=_test):
                return func(*args, **kwargs)
        return wrapper
    else:
        return Transaction().set_context(active_test=_test)


def inactive_records(func=None):
    return active_records(func=func, _test=False)


class _AttributeManager(object):
    '''
    Manage Attribute of transaction
    '''

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return Transaction()

    def __exit__(self, type, value, traceback):
        for name, value in self.kwargs.items():
            setattr(Transaction(), name, value)


class _Local(local):

    def __init__(self):
        # Transaction stack control
        self.transactions = []
        self.tasks = []


class Transaction(object):
    '''
    Control the transaction
    '''

    _local = _Local()

    cache_keys = {'language', 'fuzzy_translation', '_datetime'}

    def __new__(cls, new=False):
        transactions = cls._local.transactions
        if new or not transactions:
            instance = super(Transaction, cls).__new__(cls)
            instance.database = None
            instance.readonly = False
            instance.connection = None
            instance.close = None
            instance.user = None
            instance.context = None
            instance.create_records = None
            instance.delete_records = None
            instance.trigger_records = None
            instance.log_records = None
            instance.check_warnings = None
            instance.timestamp = None
            instance.started_at = None
            instance.cache = WeakValueDictionary()
            instance._cache_deque = deque(maxlen=_cache_transaction)
            instance._atexit = []
            transactions.append(instance)
        else:
            instance = transactions[-1]
        return instance

    @staticmethod
    def monotonic_time():
        try:
            return time.monotonic_ns()
        except AttributeError:
            return time.monotonic()

    @property
    def tasks(self):
        return self._local.tasks

    def get_cache(self):
        from trytond.cache import LRUDict
        from trytond.pool import Pool
        keys = tuple(((key, self.context[key])
                for key in sorted(self.cache_keys)
                if key in self.context))
        cache = self.cache.setdefault(
            (self.user, keys), LRUDict(
                _cache_model,
                lambda name: LRUDict(
                    record_cache_size(self),
                    Pool().get(name)._record),
                default_factory_with_key=True))
        # Keep last used cache references to allow to pre-fill them
        self._cache_deque.append(cache)
        return cache

    def start(self, database_name, user, readonly=False, context=None,
            close=False, autocommit=False, timeout=None, **extras):
        '''
        Start transaction
        '''
        try:
            from trytond import backend
            assert self.user is None
            assert self.database is None
            assert self.close is None
            assert self.context is None
            # Compute started_at before connect to ensure
            # it is strictly before all transactions started after
            # but it may be also before transactions started before
            self.started_at = self.monotonic_time()
            if not database_name:
                database = backend.Database().connect()
            else:
                database = backend.Database(database_name).connect()
            Flavor.set(backend.Database.flavor)
            self.user = user
            self.database = database
            self.readonly = readonly
            self.close = close
            self.context = ImmutableDict(context or {})
            self.create_records = defaultdict(set)
            self.delete_records = defaultdict(set)
            self.trigger_records = defaultdict(set)
            self.log_records = []
            self.check_warnings = set()
            self.timestamp = {}
            self.counter = 0
            self._datamanagers = []

            count = 0
            while True:
                if count:
                    time.sleep(0.002 * (_retry - count))
                self.connection = database.get_connection(readonly=readonly,
                    autocommit=autocommit, statement_timeout=timeout)
                try:
                    lock_tables = extras.get('_lock_tables', [])
                    for table in lock_tables:
                        self.database.lock(self.connection, table)
                    self._locked_tables = set(lock_tables)
                except backend.DatabaseOperationalError:
                    if count < _retry:
                        self.connection.rollback()
                        count += 1
                        logger.debug("Retry: %i", count)
                        continue
                    raise
                break
            if database_name:
                from trytond.cache import Cache
                Cache.sync(self)
        except BaseException:
            self.stop(False)
            raise
        return self

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.stop(type is None)

    def stop(self, commit=False):
        transactions = self._local.transactions
        try:
            if transactions.count(self) == 1:
                try:
                    try:
                        if commit and not self.readonly:
                            self.commit()
                        else:
                            self.rollback()
                    finally:
                        if self.connection:
                            self.database.put_connection(
                                self.connection, self.close)
                finally:
                    self.database = None
                    self.readonly = False
                    self.connection = None
                    self.close = None
                    self.user = None
                    self.context = None
                    self.create_records = None
                    self.delete_records = None
                    self.trigger_records = None
                    self.log_records = None
                    self.timestamp = None
                    self._datamanagers = []

                for func, args, kwargs in self._atexit:
                    func(*args, **kwargs)
        finally:
            transactions.reverse()
            try:
                transactions.remove(self)
            finally:
                transactions.reverse()

    def set_context(self, context=None, **kwargs):
        if context is None:
            context = {}
        manager = _AttributeManager(context=self.context)
        ctx = self.context.copy()
        ctx.update(context)
        if kwargs:
            ctx.update(kwargs)
        self.context = ImmutableDict(ctx)
        return manager

    def reset_context(self):
        manager = _AttributeManager(context=self.context)
        self.context = ImmutableDict()
        return manager

    def set_user(self, user, set_context=False):
        if user != 0 and set_context:
            raise ValueError('set_context only allowed for root')
        manager = _AttributeManager(user=self.user,
                context=self.context)
        ctx = self.context.copy()
        if set_context:
            if user != self.user:
                ctx['user'] = self.user
        else:
            ctx.pop('user', None)
        self.context = ImmutableDict(ctx)
        self.user = user
        return manager

    def lock_table(self, table):
        if table not in self._locked_tables:
            raise _TransactionLockError(table)

    def set_current_transaction(self, transaction):
        self._local.transactions.append(transaction)
        return transaction

    def new_transaction(self, autocommit=False, readonly=False, **extras):
        transaction = Transaction(new=True)
        return transaction.start(self.database.name, self.user,
            context=self.context, close=self.close, readonly=readonly,
            autocommit=autocommit, **extras)

    def _store_log_records(self):
        from trytond.pool import Pool
        if self.log_records:
            pool = Pool()
            Log = pool.get('ir.model.log')
            with without_check_access():
                Log.save(self.log_records)
        self._clear_log_records()

    def _clear_log_records(self):
        if self.log_records:
            self.log_records.clear()

    def commit(self):
        from trytond.cache import Cache
        try:
            self._store_log_records()
            if self._datamanagers:
                for datamanager in self._datamanagers:
                    datamanager.tpc_begin(self)
                for datamanager in self._datamanagers:
                    datamanager.commit(self)
                for datamanager in self._datamanagers:
                    datamanager.tpc_vote(self)
            self.started_at = self.monotonic_time()
            for cache in self.cache.values():
                cache.clear()
            Cache.commit(self)
            self.connection.commit()
        except Exception:
            self.rollback()
            raise
        else:
            try:
                for datamanager in self._datamanagers:
                    datamanager.tpc_finish(self)
            except Exception:
                logger.critical('A datamanager raised an exception in'
                    ' tpc_finish, the data might be inconsistant',
                    exc_info=True)

    def rollback(self):
        from trytond.cache import Cache
        for cache in self.cache.values():
            cache.clear()
        for datamanager in self._datamanagers:
            datamanager.tpc_abort(self)
        Cache.rollback(self)
        self._clear_log_records()
        if self.connection:
            self.connection.rollback()

    def join(self, datamanager):
        try:
            idx = self._datamanagers.index(datamanager)
            return self._datamanagers[idx]
        except ValueError:
            self._datamanagers.append(datamanager)
            return datamanager

    def atexit(self, func, *args, **kwargs):
        self._atexit.append((func, args, kwargs))

    @property
    def language(self):
        def get_language():
            from trytond.pool import Pool
            Config = Pool().get('ir.configuration')
            return Config.get_language()
        if self.context:
            return self.context.get('language') or get_language()
        return get_language()

    @property
    def check_access(self):
        return self.context.get('_check_access', False)

    @property
    def active_records(self):
        return self.context.get('active_test', True)
