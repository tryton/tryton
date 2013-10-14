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
import datetime
import time


def dump_decimal(self, value, write):
    value = {'__class__': 'Decimal',
        'decimal': str(value),
        }
    self.dump_struct(value, write)


def dump_buffer(self, value, write):
    self.write = write
    value = xmlrpclib.Binary(value)
    value.encode(self)
    del self.write


def dump_date(self, value, write):
    value = {'__class__': 'date',
        'year': value.year,
        'month': value.month,
        'day': value.day,
        }
    self.dump_struct(value, write)


def dump_time(self, value, write):
    value = {'__class__': 'time',
        'hour': value.hour,
        'minute': value.minute,
        'second': value.second,
        }
    self.dump_struct(value, write)

xmlrpclib.Marshaller.dispatch[Decimal] = dump_decimal
xmlrpclib.Marshaller.dispatch[datetime.date] = dump_date
xmlrpclib.Marshaller.dispatch[datetime.time] = dump_time
xmlrpclib.Marshaller.dispatch[buffer] = dump_buffer


def end_struct(self, data):
    mark = self._marks.pop()
    # map structs to Python dictionaries
    dct = {}
    items = self._stack[mark:]
    for i in range(0, len(items), 2):
        dct[xmlrpclib._stringify(items[i])] = items[i + 1]
    if '__class__' in dct:
        if dct['__class__'] == 'date':
            dct = datetime.date(dct['year'], dct['month'], dct['day'])
        elif dct['__class__'] == 'time':
            dct = datetime.time(dct['hour'], dct['minute'], dct['second'])
        elif dct['__class__'] == 'Decimal':
            dct = Decimal(dct['decimal'])
    self._stack[mark:] = [dct]
    self._value = 0

xmlrpclib.Unmarshaller.dispatch['struct'] = end_struct

_CONFIG = threading.local()
_CONFIG.current = None


class ContextManager(object):
    'Context Manager for the tryton context'

    def __init__(self, config):
        self.config = config
        self.context = config.context

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.config._context = self.context


class Config(object):
    'Config interface'

    def __init__(self):
        super(Config, self).__init__()
        self._context = {}

    @property
    def context(self):
        return self._context.copy()

    def set_context(self, context=None, **kwargs):
        ctx_manager = ContextManager(self)

        if context is None:
            context = {}
        self._context = self.context
        self._context.update(context)
        self._context.update(kwargs)
        return ctx_manager

    def get_proxy(self, name):
        raise NotImplementedError

    def get_proxy_methods(self, name):
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
        from trytond.rpc import RPC

        if self._name in self._object.__rpc__:
            rpc = self._object.__rpc__[self._name]
        elif self._name in getattr(self._object, '_buttons', {}):
            rpc = RPC(readonly=False, instantiate=0)
        else:
            raise TypeError('%s is not callable' % self._name)

        with Transaction().start(self._config.database_name,
                self._config.user, readonly=rpc.readonly) as transaction:
            Cache.clean(self._config.database_name)
            args, kwargs, transaction.context, transaction.timestamp = \
                rpc.convert(self._object, *args)
            meth = getattr(self._object, self._name)
            if not hasattr(meth, 'im_self') or meth.im_self:
                result = rpc.result(meth(*args, **kwargs))
            else:
                assert rpc.instantiate == 0
                inst = args.pop(0)
                if hasattr(inst, self._name):
                    result = rpc.result(meth(inst, *args, **kwargs))
                else:
                    result = [rpc.result(meth(i, *args, **kwargs))
                        for i in inst]
            if not rpc.readonly:
                transaction.cursor.commit()
        Cache.resets(self._config.database_name)
        return result


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

    def __init__(self, database_name=None, user='admin', database_type=None,
            language='en_US', password='', config_file=None):
        super(TrytondConfig, self).__init__()
        from trytond.config import CONFIG
        CONFIG.update_etc(config_file)
        CONFIG.set_timezone()
        if database_type is not None:
            CONFIG['db_type'] = database_type
        from trytond.pool import Pool
        from trytond import backend
        from trytond.protocols.dispatcher import create
        from trytond.cache import Cache
        from trytond.transaction import Transaction
        self.database_type = CONFIG['db_type']
        if database_name is None:
            if self.database_type == 'sqlite':
                database_name = ':memory:'
            else:
                database_name = 'test_%s' % int(time.time())
        self.database_name = database_name
        self._user = user
        self.config_file = config_file

        Pool.start()

        with Transaction().start(None, 0) as transaction:
            cursor = transaction.cursor
            databases = backend.get('Database').list(cursor)
        if database_name not in databases:
            create(database_name, CONFIG['admin_passwd'], language, password)

        database_list = Pool.database_list()
        self.pool = Pool(database_name)
        if database_name not in database_list:
            self.pool.init()

        with Transaction().start(self.database_name, 0) as transaction:
            Cache.clean(database_name)
            User = self.pool.get('res.user')
            transaction.context = self.context
            self.user = User.search([
                ('login', '=', user),
                ], limit=1)[0].id
            with transaction.set_user(self.user):
                self._context = User.get_preferences(context_only=True)
        Cache.resets(database_name)
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return "proteus.config.TrytondConfig"\
            "('%s', '%s', '%s', config_file=%s)"\
            % (self.database_name, self._user, self.database_type,
                self.config_file)
    __repr__.__doc__ = object.__repr__.__doc__

    def __eq__(self, other):
        if not isinstance(other, TrytondConfig):
            raise NotImplementedError
        return (self.database_name == other.database_name
            and self._user == other._user
            and self.database_type == other.database_type
            and self.config_file == other.config_file)

    def __hash__(self):
        return hash((self.database_name, self._user,
            self.database_type, self.config_file))

    def get_proxy(self, name, type='model'):
        'Return Proxy class'
        return TrytondProxy(name, self, type=type)

    def get_proxy_methods(self, name, type='model'):
        'Return list of methods'
        proxy = self.get_proxy(name, type=type)
        methods = [x for x in proxy._object.__rpc__]
        if hasattr(proxy._object, '_buttons'):
            methods += [x for x in proxy._object._buttons]
        return methods


def set_trytond(database_name=None, user='admin', database_type=None,
        language='en_US', password='', config_file=None):
    'Set trytond package as backend'
    _CONFIG.current = TrytondConfig(database_name, user, database_type,
            language=language, password=password, config_file=config_file)
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

    def __eq__(self, other):
        if not isinstance(other, XmlrpcConfig):
            raise NotImplementedError
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

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
    return _CONFIG.current
