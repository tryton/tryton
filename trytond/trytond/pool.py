#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.modules import load_modules, register_classes
from threading import RLock
import logging


class Pool(object):

    classes = {
        'model': {},
        'wizard': {},
        'report': {},
    }
    _lock = RLock()
    _locks = {}
    _pool = {}
    _pools = {}
    test = False

    def __new__(cls, database_name):
        cls._lock.acquire()
        lock = cls._locks.setdefault(database_name, RLock())
        cls._lock.release()
        lock.acquire()
        if database_name in cls._pools:
            res = cls._pools[database_name]
            lock.release()
            return res
        lock.release()
        return object.__new__(cls)

    def __init__(self, database_name):
        self.database_name = database_name
        self._lock.acquire()
        lock = self._locks.setdefault(database_name, RLock())
        self._lock.release()
        lock.acquire()
        self._pool.setdefault(database_name, {})
        for type in self.classes.keys():
            self._pool[database_name].setdefault(type, {})
        self._pools.setdefault(database_name, self)
        lock.release()

    @staticmethod
    def register(klass, type='model'):
        '''
        Register a class

        :param klass: the class
        :param type: the type
        '''
        module = None
        for module in klass.__module__.split('.'):
            if module != 'trytond' and module != 'modules':
                break
        if module:
            Pool.classes[type].setdefault(module, []).append(klass)

    @staticmethod
    def start():
        '''
        Start/restart the Pool
        '''
        Pool._lock.acquire()
        try:
            reload_p = False
            prev_classes = {}
            for type in Pool.classes:
                if Pool.classes[type]:
                    reload_p = True
                prev_classes[type] = Pool.classes[type]
                Pool.classes[type] = {}
            try:
                register_classes(reload_p=reload_p)
            except Exception:
                if not reload_p:
                    raise
                for type in prev_classes:
                    Pool.classes[type] = prev_classes[type]
            for db_name in Pool.database_list():
                Pool(db_name).init()
        finally:
            Pool._lock.release()

    @staticmethod
    def stop(database_name):
        '''
        Stop the Pool
        '''
        Pool._lock.acquire()
        lock = Pool._locks.setdefault(database_name, RLock())
        Pool._lock.release()
        lock.acquire()
        if database_name in Pool._pool:
            del Pool._pool[database_name]
        if database_name in Pool._pools:
            del Pool._pools[database_name]
        lock.release()

    @staticmethod
    def database_list():
        '''
        :return: database list
        '''
        return Pool._pool.keys()

    def init(self, update=False, lang=None):
        '''
        Init pool

        :param database_name: the database name
        :param update: a boolean to proceed to update
        :param lang: a list of language code to be updated
        '''
        logger = logging.getLogger('pool')
        logger.info('init pool for "%s"' % self.database_name)
        self._lock.acquire()
        lock = self._locks.setdefault(self.database_name, RLock())
        self._lock.release()
        lock.acquire()
        try:
            #Clean the _pool before loading modules
            for type in self.classes.keys():
                self._pool[self.database_name][type] = {}
            restart = not load_modules(self.database_name, self, update=update,
                    lang=lang)
            if restart:
                self.init()
        finally:
            lock.release()

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
        return self._pool[self.database_name][type][name]

    def add(self, obj, type='model'):
        '''
        Add an object to the pool

        :param obj: the object
        :param type: the type
        '''
        self._pool[self.database_name][type][obj._name] = obj
        obj.pool = self

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

    def instanciate(self, module):
        '''
        Instanciate objects for a module

        :param: the module name
        :return: a dictionary with each type as key
            and a list of object as value
        '''
        res = {}
        for _type in self.classes.keys():
            res[_type] = []
            for cls in self.classes[_type].get(module, []):
                if cls._name in self._pool[self.database_name][_type].keys():
                    parent_cls = self.get(cls._name, type=_type).__class__
                    cls = type(cls._name, (cls, parent_cls), {})
                obj = object.__new__(cls)
                self.add(obj, type=_type)
                obj.__init__()
                res[_type].append(obj)
        return res
