# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import builtins
import logging
from collections import OrderedDict, defaultdict
from threading import RLock, local
from weakref import WeakSet

from trytond.modules import load_modules, register_classes
from trytond.transaction import Transaction

__all__ = ['Pool', 'PoolMeta', 'PoolBase', 'isregisteredby']

logger = logging.getLogger(__name__)


class PoolMeta(type):

    def __new__(cls, name, bases, dct):
        if '__slots__' not in dct and not dct.get('__no_slots__'):
            dct['__slots__'] = ()
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
    __slots__ = ('database_name', '_modules', '_pool', '__weakref__')

    classes = {
        'model': defaultdict(OrderedDict),
        'wizard': defaultdict(OrderedDict),
        'report': defaultdict(OrderedDict),
    }
    classes_mixin = defaultdict(list)
    _started = False
    _lock = RLock()
    _local = local()
    _pools = defaultdict(lambda: defaultdict(dict))
    _pool_modules = defaultdict(list)
    _pool_instances = WeakSet()
    test = False

    def __new__(cls, database_name=None):
        if database_name is None:
            database_name = Transaction().database.name
        instances = cls._local.__dict__.setdefault('instances', {})
        if (instance := instances.get(database_name)) is None:
            instances[database_name] = instance = super().__new__(cls)
        if instance not in cls._pool_instances:
            with cls._lock:
                instance._pool = cls._pools[database_name]
                instance._modules = cls._pool_modules[database_name]
                cls._pool_instances.add(instance)
        return instance

    def __init__(self, database_name=None):
        if database_name is None:
            database_name = Transaction().database.name
        self.database_name = database_name

    @staticmethod
    def register(*classes, **kwargs):
        '''
        Register a list of classes
        '''
        with Pool._lock:
            module = kwargs['module']
            type_ = kwargs['type_']
            depends = set(kwargs.get('depends', []))
            assert type_ in {'model', 'report', 'wizard'}, (
                f"{type_} is not a valid type_")
            for cls in classes:
                mpool = Pool.classes[type_][module]
                assert cls not in mpool, f"{cls} is already registered"
                assert issubclass(cls.__class__, PoolMeta), (
                    f"{cls} is missing metaclass {PoolMeta}")
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
            register_classes(with_test=cls.test)
            cls._started = True

    @classmethod
    def stop(cls, database_name):
        '''
        Stop the Pool
        '''
        with cls._lock:
            cls._pools.pop(database_name, None)
            cls._pool_instances.clear()

    @classmethod
    def database_list(cls):
        '''
        :return: database list
        '''
        with cls._lock:
            return list(cls._pools.keys())

    def init(self, update=None, lang=None, activatedeps=False, indexes=None):
        '''
        Init pool
        Set update to proceed to update
        lang is a list of language code to be updated
        indexes is a boolean specifying if the indexes should be created
        '''
        with self._lock:
            if not self._started:
                self.start()
            logger.info('init pool for "%s"', self.database_name)
            # Clear before loading modules
            self._pool = defaultdict(dict)
            self._modules = []
            restart = not load_modules(
                self.database_name, self, update=update, lang=lang,
                activatedeps=activatedeps, indexes=indexes)
            self._pools[self.database_name] = self._pool
            self._pool_modules[self.database_name] = self._modules
            self._pool_instances.clear()
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
                if name in self._pool[type]:
                    break
        try:
            return self._pool[type][name]
        except KeyError:
            if type == 'report':
                from trytond.report import Report

                # Keyword argument 'type' conflicts with builtin function
                cls = builtins.type(name, (Report,), {'__slots__': ()})
                cls.__setup__()
                cls.__post_setup__()
                self.add(cls, type)
                self.setup_mixin(type='report', name=name)
                return self.get(name, type=type)
            raise

    def add(self, cls, type='model'):
        '''
        Add a classe to the pool
        '''
        self._pool[type][cls.__name__] = cls

    def iterobject(self, type='model'):
        '''
        Return an iterator over object name, object

        :param type: the type
        :return: an iterator
        '''
        return self._pool[type].items()

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
                    cls = type(
                        cls.__name__, (cls, previous_cls), {'__slots__': ()})
                except KeyError:
                    pass
                assert issubclass(cls, PoolBase), (
                    f"{cls} is not a subclass of {PoolBase}")
                self.add(cls, type=type_)
                classes[type_].append(cls)
        self._modules.append(module)
        return classes

    def setup(self, classes=None):
        logger.info('setup pool for "%s"', self.database_name)
        if classes is None:
            classes = {}
            for type_ in self._pool:
                classes[type_] = list(self._pool[type_].values())
        for type_, lst in classes.items():
            for cls in lst:
                cls.__setup__()
            for cls in lst:
                cls.__post_setup__()

    def setup_mixin(self, type=None, name=None):
        logger.info('setup mixin for "%s"', self.database_name)
        if type is not None:
            types = [type]
        else:
            types = self.classes.keys()
        for module in self._modules:
            if module not in self.classes_mixin:
                continue
            for type_ in types:
                for kname, cls in self.iterobject(type=type_):
                    if name is not None and kname != name:
                        continue
                    for parent, mixin in self.classes_mixin[module]:
                        if (not issubclass(cls, parent)
                                or issubclass(cls, mixin)):
                            continue
                        cls = builtins.type(
                            cls.__name__, (mixin, cls), {'__slots__': ()})
                        self.add(cls, type=type_)

    @classmethod
    def refresh(cls, database_name, modules):
        if (cls._pool_modules[database_name]
                and set(cls._pool_modules[database_name]) != set(modules)):
            cls.stop(database_name)


def isregisteredby(obj, module, type_='model'):
    pool = Pool()
    classes = pool.classes[type_]
    return any(issubclass(obj, cls) for cls in classes[module])
