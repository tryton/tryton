#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"""
Configuration functions for the proteus package for Tryton.
"""
import xmlrpclib
import threading
from decimal import Decimal
from types import NoneType
import datetime

xmlrpclib.Marshaller.dispatch[Decimal] = \
        lambda self, value, write: self.dump_double(float(value), write)
xmlrpclib.Marshaller.dispatch[datetime.date] = \
        lambda self, value, write: self.dump_datetime(
                datetime.datetime.combine(value, datetime.time()), write)

_CONFIG = threading.local()


class Config(object):
    'Config interface'

    def __init__(self):
        super(Config, self).__init__()
        self._context = {}

    @property
    def context(self):
        return self._context.copy()

    def get_proxy(self, name):
        raise NotImplementedError

    def get_proxy_methods(self, name):
        raise NotImplementedError

class _TrytondMethod(object):

    def __init__(self, name, model, config):
        super(_TrytondMethod, self).__init__()
        self._name = name
        self._model = model
        self._config = config

    def __call__(self, *args):
        from trytond.tools import Cache

        assert self._name in self._model._rpc

        Cache.clean(self._config.database.database_name)
        cursor = self._config.database.cursor()
        try:
            res = getattr(self._model, self._name)(cursor, self._config.user,
                    *args)
            if self._model._rpc[self._name]:
                cursor.commit()
            return res
        finally:
            cursor.close()
            Cache.resets(self._config.database.database_name)

class TrytondProxy(object):
    'Proxy for function call for trytond'

    def __init__(self, name, config):
        super(TrytondProxy, self).__init__()
        self._config = config
        self._model = config.pool.get(name)
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return _TrytondMethod(name, self._model, self._config)


class TrytondConfig(Config):
    'Configuration for trytond'

    def __init__(self, database_name, user, database_type, language='en_US',
            password=''):
        super(TrytondConfig, self).__init__()
        from trytond.config import CONFIG
        CONFIG['db_type'] = database_type
        CONFIG.parse()
        from trytond.modules import register_classes
        from trytond.pool import Pool
        from trytond.backend import Database
        from trytond.protocols.dispatcher import create
        from trytond.tools import Cache
        self.database_name = database_name
        self._user = user
        self.database_type = database_type

        register_classes()

        database = Database().connect()
        cursor = database.cursor()
        try:
            databases = database.list(cursor)
        finally:
            cursor.close()
        if database_name not in databases:
            create(database_name, CONFIG['admin_passwd'], language, password)

        self.database = Database(database_name).connect()
        database_list = Pool.database_list()
        self.pool = Pool(database_name)
        if database_name not in database_list:
            self.pool.init()

        Cache.clean(database_name)
        user_obj = self.pool.get('res.user')
        cursor = self.database.cursor()
        try:
            self.user = user_obj.search(cursor, 0, [
                ('login', '=', user),
                ], context=self.context, limit=1)[0]
            self._context = user_obj.get_preferences(cursor, self.user,
                    context_only=True, context=self.context)
        finally:
            cursor.close()
            Cache.resets(database_name)
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return "proteus.config.TrytondConfig('%s', '%s', '%s')" % (
                self.database_name, self._user, self.database_type)
    __repr__.__doc__ = object.__repr__.__doc__

    def get_proxy(self, name):
        'Return Proxy class'
        return TrytondProxy(name, self)

    def get_proxy_methods(self, name):
        'Return list of methods'
        proxy = self.get_proxy(name)
        return [x for x in proxy._model._rpc]

def set_trytond(database_name, user='admin', database_type='postgresql',
        language='en_US', password=''):
    'Set trytond package as backend'
    _CONFIG.current = TrytondConfig(database_name, user, database_type,
            language=language, password=password)
    return _CONFIG.current


class XmlrpcProxy(object):
    'Proxy for function call for XML-RPC'

    def __init__(self, name, config):
        super(XmlrpcProxy, self).__init__()
        self._config = config
        self._model = getattr(config.server, 'model.%s' % name)
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return getattr(self._model, name)

class XmlrpcConfig(Config):
    'Configuration for XML-RPC'

    def __init__(self, url):
        super(XmlrpcConfig, self).__init__()
        self.url = url
        self.server = xmlrpclib.ServerProxy(url, allow_none=1, use_datetime=1)
        # TODO add user
        self._context = self.server.model.res.user.get_preferences(True, {})
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return "proteus.config.XmlrpcConfig('%s')" % self.url
    __repr__.__doc__ = object.__repr__.__doc__

    def get_proxy(self, name):
        'Return Proxy class'
        return XmlrpcProxy(name, self)

    def get_proxy_methods(self, name):
        'Return list of methods'
        return [x[len('model.%s' % name) + 1:]
                for x in self.server.system.listMethods()
                if x.startswith('model.%s' % name)
                and '.' not in x[len('model.%s' % name) + 1:]]

def set_xmlrpc(url):
    'Set XML-RPC as backend'
    _CONFIG.current = XmlrpcConfig(url)
    return _CONFIG.current

def get_config():
    # TODO raise exception if not set
    return _CONFIG.current
