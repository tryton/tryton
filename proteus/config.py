#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"""
Configuration functions for the proteus package for Tryton.
"""
from __future__ import with_statement
__all__ = ['set_trytond', 'set_xmlrpc', 'get_config']
import xmlrpclib
import threading
from decimal import Decimal
from types import NoneType
import datetime

def dump_decimal(self, value, write):
    write("<value><double>")
    write(str(value))
    write("</double></value>\n")

xmlrpclib.Marshaller.dispatch[Decimal] = dump_decimal
xmlrpclib.Marshaller.dispatch[datetime.date] = \
        lambda self, value, write: self.dump_datetime(
                datetime.datetime.combine(value, datetime.time()), write)

def _end_double(self, data):
    self.append(Decimal(data))
    self._value = 0
xmlrpclib.Unmarshaller.dispatch["double"] = _end_double

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

    def __eq__(self, other):
        if isinstance(other, Config):
            return repr(self) == repr(other)
        raise NotImplementedError


class _TrytondMethod(object):

    def __init__(self, name, model, config):
        super(_TrytondMethod, self).__init__()
        self._name = name
        self._object = model
        self._config = config

    def __call__(self, *args):
        from trytond.cache import Cache
        from trytond.transaction import Transaction

        assert self._name in self._object._rpc

        with Transaction().start(self._config.database_name,
                self._config.user) as transaction:
            Cache.clean(self._config.database_name)
            args = list(args)
            context = args.pop()
            if '_timestamp' in context:
                transaction.timestamp = context['_timestamp']
                del context['_timestamp']
            transaction.context = context
            res = getattr(self._object, self._name)(*args)
            if self._object._rpc[self._name]:
                transaction.cursor.commit()
        Cache.resets(self._config.database_name)
        return res

class TrytondProxy(object):
    'Proxy for function call for trytond'

    def __init__(self, name, config, type='model'):
        super(TrytondProxy, self).__init__()
        self._config = config
        self._object = config.pool.get(name, type=type)
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return _TrytondMethod(name, self._object, self._config)


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
        from trytond.cache import Cache
        from trytond.transaction import Transaction
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

        database_list = Pool.database_list()
        self.pool = Pool(database_name)
        if database_name not in database_list:
            self.pool.init()

        with Transaction().start(self.database_name, 0) as transaction:
            Cache.clean(database_name)
            user_obj = self.pool.get('res.user')
            transaction.context = self.context
            self.user = user_obj.search([
                ('login', '=', user),
                ], limit=1)[0]
            with transaction.set_user(self.user):
                self._context = user_obj.get_preferences(context_only=True)
        Cache.resets(database_name)
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return "proteus.config.TrytondConfig('%s', '%s', '%s')" % (
                self.database_name, self._user, self.database_type)
    __repr__.__doc__ = object.__repr__.__doc__

    def get_proxy(self, name, type='model'):
        'Return Proxy class'
        return TrytondProxy(name, self, type=type)

    def get_proxy_methods(self, name, type='model'):
        'Return list of methods'
        proxy = self.get_proxy(name, type=type)
        return [x for x in proxy._object._rpc]

def set_trytond(database_name, user='admin', database_type='postgresql',
        language='en_US', password=''):
    'Set trytond package as backend'
    _CONFIG.current = TrytondConfig(database_name, user, database_type,
            language=language, password=password)
    return _CONFIG.current


class XmlrpcProxy(object):
    'Proxy for function call for XML-RPC'

    def __init__(self, name, config, type='model'):
        super(XmlrpcProxy, self).__init__()
        self._config = config
        self._object = getattr(config.server, '%s.%s' % (type, name))
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return getattr(self._object, name)

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

    def get_proxy(self, name, type='model'):
        'Return Proxy class'
        return XmlrpcProxy(name, self, type=type)

    def get_proxy_methods(self, name, type='model'):
        'Return list of methods'
        object_ = '%s.%s' % (type, name)
        return [x[len(object_) + 1:]
                for x in self.server.system.listMethods()
                if x.startswith(object_)
                and '.' not in x[len(object_) + 1:]]

def set_xmlrpc(url):
    'Set XML-RPC as backend'
    _CONFIG.current = XmlrpcConfig(url)
    return _CONFIG.current

def get_config():
    # TODO raise exception if not set
    return _CONFIG.current
