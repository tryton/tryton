#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from threading import RLock
import logging
from trytond.modules import load_modules, register_classes
from trytond.transaction import Transaction
import __builtin__


class Pool(object):

    classes = {
        'model': {},
        'wizard': {},
        'report': {},
    }
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

    @classmethod
    def start(cls):
        '''
        Start/restart the Pool
        '''
        with cls._lock:
            reload_p = False
            prev_classes = {}
            for type in cls.classes:
                if cls.classes.get(type):
                    reload_p = True
                prev_classes[type] = cls.classes.get(type)
                cls.classes[type] = {}
            try:
                register_classes(reload_p=reload_p)
            except Exception:
                if not reload_p:
                    raise
                for type in prev_classes:
                    cls.classes[type] = prev_classes[type]
            for db_name in cls.database_list():
                cls(db_name).init()

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
        return cls._pool.keys()

    def init(self, update=False, lang=None):
        '''
        Init pool

        :param database_name: the database name
        :param update: a boolean to proceed to update
        :param lang: a list of language code to be updated
        '''
        logger = logging.getLogger('pool')
        logger.info('init pool for "%s"' % self.database_name)
        with self._locks[self.database_name]:
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
                obj = object.__new__(cls)
                obj._name = name
                self.add(obj, type)
                obj.__init__()
                return obj
            raise

    def add(self, obj, type='model'):
        '''
        Add an object to the pool

        :param obj: the object
        :param type: the type
        '''
        with self._locks[self.database_name]:
            self._pool[self.database_name][type][obj._name] = obj

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
