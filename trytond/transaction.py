# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from threading import local
from sql import Flavor

from trytond.tools.singleton import Singleton
from trytond import backend


class _TransactionManager(object):
    '''
    Manage transaction start/stop
    '''

    def __enter__(self):
        return Transaction()

    def __exit__(self, type, value, traceback):
        Transaction().stop()


class _AttributeManager(object):
    '''
    Manage Attribute of transaction
    '''

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return Transaction()

    def __exit__(self, type, value, traceback):
        for name, value in self.kwargs.iteritems():
            setattr(Transaction(), name, value)


class _CursorManager(object):
    '''
    Manage cursor of transaction
    '''

    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return Transaction()

    def __exit__(self, type, value, traceback):
        Transaction().cursor.close()
        Transaction().cursor = self.cursor


class Transaction(local):
    '''
    Control the transaction
    '''
    __metaclass__ = Singleton

    cursor = None
    database = None
    close = None
    user = None
    context = None
    create_records = None
    delete_records = None
    delete = None  # TODO check to merge with delete_records
    timestamp = None

    def start(self, database_name, user, readonly=False, context=None,
            close=False, autocommit=False):
        '''
        Start transaction
        '''
        Database = backend.get('Database')
        assert self.user is None
        assert self.database is None
        assert self.cursor is None
        assert self.close is None
        assert self.context is None
        if not database_name:
            database = Database().connect()
        else:
            database = Database(database_name).connect()
        Flavor.set(Database.flavor)
        cursor = database.cursor(readonly=readonly,
            autocommit=autocommit)
        self.user = user
        self.database = database
        self.cursor = cursor
        self.close = close
        self.context = context or {}
        self.create_records = {}
        self.delete_records = {}
        self.delete = {}
        self.timestamp = {}
        self.counter = 0
        return _TransactionManager()

    def stop(self):
        '''
        Stop transaction
        '''
        try:
            self.cursor.close(close=self.close)
        finally:
            self.cursor = None
            self.database = None
            self.close = None
            self.user = None
            self.context = None
            self.create_records = None
            self.delete_records = None
            self.delete = None
            self.timestamp = None

    def set_context(self, context=None, **kwargs):
        if context is None:
            context = {}
        manager = _AttributeManager(context=self.context)
        self.context = self.context.copy()
        self.context.update(context)
        if kwargs:
            self.context.update(kwargs)
        return manager

    def reset_context(self):
        manager = _AttributeManager(context=self.context)
        self.context = {}
        return manager

    def set_user(self, user, set_context=False):
        if user != 0 and set_context:
            raise ValueError('set_context only allowed for root')
        manager = _AttributeManager(user=self.user,
                context=self.context)
        self.context = self.context.copy()
        if set_context:
            if user != self.user:
                self.context['user'] = self.user
        else:
            self.context.pop('user', None)
        self.user = user
        return manager

    def set_cursor(self, cursor):
        manager = _AttributeManager(cursor=self.cursor)
        self.cursor = cursor
        return manager

    def new_cursor(self, autocommit=False, readonly=False):
        Database = backend.get('Database')
        manager = _CursorManager(self.cursor)
        database = Database(self.cursor.database_name).connect()
        self.cursor = database.cursor(autocommit=autocommit, readonly=readonly)
        return manager

    @property
    def language(self):
        def get_language():
            from trytond.pool import Pool
            Config = Pool().get('ir.configuration')
            return Config.get_language()
        if self.context:
            return self.context.get('language') or get_language()
        return get_language()
