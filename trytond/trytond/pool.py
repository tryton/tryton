# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict, OrderedDict
from threading import RLock
import logging
from trytond.modules import load_modules, register_classes
from trytond.transaction import Transaction
import builtins

__all__ = ['Pool', 'PoolMeta', 'PoolBase', 'isregisteredby']

logger = logging.getLogger(__name__)


class PoolMeta(type):

    def __new__(cls, name, bases, dct):
        new = type.__new__(cls, name, bases, dct)
        if '__name__' in dct:
            try:
                new.__name__ = dct['__name__']
            except TypeError:
                new.__name__ = dct['__name__'].encode('utf-8')
        return new


class PoolBase(object, metaclass=PoolMeta):
    @classmethod
    def __setup__(cls):
        pass

    @classmethod
    def __post_setup__(cls):
        pass

    @classmethod
    def __register__(cls, module_name):
        pass


class Pool(object):

    classes = {
        'model': defaultdict(OrderedDict),
        'wizard': defaultdict(OrderedDict),
        'report': defaultdict(OrderedDict),
    }
    classes_mixin = defaultdict(list)
    _started = False
    _lock = RLock()
    _locks = {}
    _pool = {}
    test = False
    _instances = {}

    def __new__(cls, database_name=None):
        if database_name is None:
            database_name = Transaction().database.name
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
            database_name = Transaction().database.name
        self.database_name = database_name

    @staticmethod
    def register(*classes, **kwargs):
        '''
        Register a list of classes
        '''
        module = kwargs['module']
        type_ = kwargs['type_']
        depends = set(kwargs.get('depends', []))
        assert type_ in ('model', 'report', 'wizard')
        for cls in classes:
            mpool = Pool.classes[type_][module]
            assert cls not in mpool, cls
            assert issubclass(cls.__class__, PoolMeta), cls
            mpool[cls] = depends

    @staticmethod
    def register_mixin(mixin, classinfo, module):
        Pool.classes_mixin[module].append((classinfo, mixin))

    @classmethod
    def start(cls):
        '''
        Start/restart the Pool
        '''
        with cls._lock:
            for classes in Pool.classes.values():
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

    def init(self, update=None, lang=None, activatedeps=False):
        '''
        Init pool
        Set update to proceed to update
        lang is a list of language code to be updated
        '''
        with self._lock:
            if not self._started:
                self.start()
        with self._locks[self.database_name]:
            # Don't reset pool if already init and not to update
            if not update and self._pool.get(self.database_name):
                return
            logger.info('init pool for "%s"', self.database_name)
            self._pool.setdefault(self.database_name, {})
            # Clean the _pool before loading modules
            for type in self.classes.keys():
                self._pool[self.database_name][type] = {}
            restart = not load_modules(self.database_name, self, update=update,
                    lang=lang, activatedeps=activatedeps)
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
                cls = builtins.type(str(name), (Report,), {})
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

    def iterobject(self, type='model'):
        '''
        Return an iterator over object name, object

        :param type: the type
        :return: an iterator
        '''
        return self._pool[self.database_name][type].items()

    def fill(self, module, modules):
        '''
        Fill the pool with the registered class from the module for the
        activated modules.
        Return a list of classes for each type in a dictionary.
        '''
        classes = {}
        for type_ in self.classes.keys():
            classes[type_] = []
            for cls, depends in self.classes[type_].get(module, {}).items():
                if not depends.issubset(modules):
                    continue
                try:
                    previous_cls = self.get(cls.__name__, type=type_)
                    cls = type(cls.__name__, (cls, previous_cls), {})
                except KeyError:
                    pass
                assert issubclass(cls, PoolBase), cls
                self.add(cls, type=type_)
                classes[type_].append(cls)
        return classes

    def setup(self, classes=None):
        logger.info('setup pool for "%s"', self.database_name)
        if classes is None:
            classes = {}
            for type_ in self._pool[self.database_name]:
                classes[type_] = list(self._pool[self.database_name][type_].values())
        for type_, lst in classes.items():
            for cls in lst:
                cls.__setup__()
            for cls in lst:
                cls.__post_setup__()

    def setup_mixin(self, modules):
        logger.info('setup mixin for "%s"', self.database_name)
        for module in modules:
            if module not in self.classes_mixin:
                continue
            for type_ in self.classes.keys():
                for _, cls in self.iterobject(type=type_):
                    for parent, mixin in self.classes_mixin[module]:
                        if (not issubclass(cls, parent)
                                or issubclass(cls, mixin)):
                            continue
                        cls = type(cls.__name__, (mixin, cls), {})
                        self.add(cls, type=type_)


def isregisteredby(obj, module, type_='model'):
    pool = Pool()
    classes = pool.classes[type_]
    return any(issubclass(obj, cls) for cls in classes[module])
