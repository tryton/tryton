#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from threading import RLock
import logging
from trytond.modules import load_modules, register_classes
from trytond.transaction import Transaction
import __builtin__

__all__ = ['Pool', 'PoolMeta']


class PoolMeta(type):

    def __new__(cls, name, bases, dct):
        new = type.__new__(cls, name, bases, dct)
        if '__name__' in dct:
            new.__name__ = dct['__name__']
        return new


class Pool(object):

    classes = {
        'model': {},
        'wizard': {},
        'report': {},
    }
    _started = False
    _lock = RLock()
    _locks = {}
    _pool = {}
    test = False
    _instances = {}

    def __new__(cls, database_name=None):
        if database_name is None:
            database_name = Transaction().cursor.database_name
        result = cls._instances.get(database_name)
        if result:
            return result
        lock = cls._locks.get(database_name)
        if not lock:
            with cls._lock:
                lock = cls._locks.setdefault(database_name, RLock())
        with lock:
            return cls._instances.setdefault(database_name,
                super(Pool, cls).__new__(cls))

    def __init__(self, database_name=None):
        if database_name is None:
            database_name = Transaction().cursor.database_name
        self.database_name = database_name

    @staticmethod
    def register(*classes, **kwargs):
        '''
        Register a list of classes
        '''
        module = kwargs['module']
        type_ = kwargs['type_']
        assert type_ in ('model', 'report', 'wizard')
        for cls in classes:
            mpool = Pool.classes[type_].setdefault(module, [])
            assert cls not in mpool, cls
            mpool.append(cls)

    @classmethod
    def start(cls):
        '''
        Start/restart the Pool
        '''
        with cls._lock:
            for classes in Pool.classes.itervalues():
                classes.clear()
            register_classes()
            cls._started = True

    @classmethod
    def stop(cls, database_name):
        '''
        Stop the Pool
        '''
        with cls._lock:
            if database_name in cls._instances:
                del cls._instances[database_name]
        lock = cls._locks.get(database_name)
        if not lock:
            return
        with lock:
            if database_name in cls._pool:
                del cls._pool[database_name]

    @classmethod
    def database_list(cls):
        '''
        :return: database list
        '''
        with cls._lock:
            databases = []
            for database in cls._pool.keys():
                if cls._locks.get(database):
                    if cls._locks[database].acquire(False):
                        databases.append(database)
                        cls._locks[database].release()
            return databases

    @property
    def lock(self):
        '''
        Return the database lock for the pool.
        '''
        return self._locks[self.database_name]

    def init(self, update=False, lang=None):
        '''
        Init pool
        Set update to proceed to update
        lang is a list of language code to be updated
        '''
        logger = logging.getLogger('pool')
        with self._lock:
            if not self._started:
                self.start()
        with self._locks[self.database_name]:
            # Don't reset pool if already init and not to update
            if not update and self._pool.get(self.database_name):
                return
            logger.info('init pool for "%s"' % self.database_name)
            self._pool.setdefault(self.database_name, {})
            #Clean the _pool before loading modules
            for type in self.classes.keys():
                self._pool[self.database_name][type] = {}
            restart = not load_modules(self.database_name, self, update=update,
                    lang=lang)
            if restart:
                self.init()

    def get(self, name, type='model'):
        '''
        Get an object from the pool

        :param name: the object name
        :param type: the type
        :return: the instance
        '''
        if type == '*':
            for type in self.classes.keys():
                if name in self._pool[self.database_name][type]:
                    break
        try:
            return self._pool[self.database_name][type][name]
        except KeyError:
            if type == 'report':
                from trytond.report import Report
                # Keyword argument 'type' conflicts with builtin function
                cls = __builtin__.type(str(name), (Report,), {})
                cls.__setup__()
                self.add(cls, type)
                return cls
            raise

    def add(self, cls, type='model'):
        '''
        Add a classe to the pool
        '''
        with self._locks[self.database_name]:
            self._pool[self.database_name][type][cls.__name__] = cls

    def object_name_list(self, type='model'):
        '''
        Return the object name list of a type

        :param type: the type
        :return: a list of name
        '''
        if type == '*':
            res = []
            for type in self.classes.keys():
                res += self._pool[self.database_name][type].keys()
            return res
        return self._pool[self.database_name][type].keys()

    def iterobject(self, type='model'):
        '''
        Return an iterator over object name, object

        :param type: the type
        :return: an iterator
        '''
        return self._pool[self.database_name][type].iteritems()

    def setup(self, module):
        '''
        Setup classes for module and return a list of classes for each type in
        a dictionary.
        '''
        classes = {}
        for type_ in self.classes.keys():
            classes[type_] = []
            for cls in self.classes[type_].get(module, []):
                try:
                    previous_cls = self.get(cls.__name__, type=type_)
                    cls = type(cls.__name__, (cls, previous_cls), {})
                except KeyError:
                    pass
                try:
                    cls.__setup__()
                except AttributeError:
                    if issubclass(cls.__class__, PoolMeta):
                        continue
                    raise
                self.add(cls, type=type_)
                classes[type_].append(cls)
            for cls in classes[type_]:
                if hasattr(cls, '__post_setup__'):
                    cls.__post_setup__()
        return classes
