# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
Configuration functions for the proteus package for Tryton.
"""

import base64
import datetime
import os
import threading
import urllib.parse
import xmlrpc.client
from contextlib import contextmanager
from decimal import Decimal

import defusedxml.xmlrpc

__all__ = ['set_trytond', 'set_xmlrpc', 'get_config']

defusedxml.xmlrpc.monkey_patch()


def dump_decimal(self, value, write):
    write('<value><bigdecimal>')
    write(str(Decimal(value)))
    write('</bigdecimal></value>')


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
        'microsecond': value.microsecond,
        }
    self.dump_struct(value, write)


def dump_timedelta(self, value, write):
    value = {'__class__': 'timedelta',
        'seconds': value.total_seconds(),
        }
    self.dump_struct(value, write)


def dump_long(self, value, write):
    try:
        self.dump_long(value, write)
    except OverflowError:
        write('<value><biginteger>')
        write(str(int(value)))
        write('</biginteger></value>\n')


xmlrpc.client.Marshaller.dispatch[Decimal] = dump_decimal
xmlrpc.client.Marshaller.dispatch[datetime.date] = dump_date
xmlrpc.client.Marshaller.dispatch[datetime.time] = dump_time
xmlrpc.client.Marshaller.dispatch[datetime.timedelta] = dump_timedelta
xmlrpc.client.Marshaller.dispatch[int] = dump_long


def dump_struct(self, value, write, escape=xmlrpc.client.escape):
    converted_value = {}
    for k, v in value.items():
        if isinstance(k, int):
            k = str(k)
        elif isinstance(k, float):
            k = repr(k)
        converted_value[k] = v
    return self.dump_struct(converted_value, write, escape=escape)


xmlrpc.client.Marshaller.dispatch[dict] = dump_struct


class XMLRPCDecoder(object):

    decoders = {}

    @classmethod
    def register(cls, klass, decoder):
        assert klass not in cls.decoders
        cls.decoders[klass] = decoder

    def __call__(self, dct):
        if dct.get('__class__') in self.decoders:
            return self.decoders[dct['__class__']](dct)
        return dct


XMLRPCDecoder.register('date',
    lambda dct: datetime.date(dct['year'], dct['month'], dct['day']))
XMLRPCDecoder.register('time',
    lambda dct: datetime.time(dct['hour'], dct['minute'], dct['second'],
        dct['microsecond']))
XMLRPCDecoder.register('timedelta',
    lambda dct: datetime.timedelta(seconds=dct['seconds']))
XMLRPCDecoder.register('Decimal', lambda dct: Decimal(dct['decimal']))


def end_struct(self, data):
    mark = self._marks.pop()
    # map structs to Python dictionaries
    dct = {}
    items = self._stack[mark:]
    for i in range(0, len(items), 2):
        dct[items[i]] = items[i + 1]
    dct = XMLRPCDecoder()(dct)
    self._stack[mark:] = [dct]
    self._value = 0


xmlrpc.client.Unmarshaller.dispatch['struct'] = end_struct

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
        super().__init__()
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

    def reset_context(self):
        ctx_manager = ContextManager(self)
        self._context = {}
        return ctx_manager

    def get_proxy(self, name):
        raise NotImplementedError

    def get_proxy_methods(self, name):
        raise NotImplementedError


class _TrytondMethod(object):

    def __init__(self, name, model, config):
        super().__init__()
        self._name = name
        self._object = model
        self._config = config

    def __call__(self, *args, **kwargs):
        from trytond.rpc import RPC, RPCReturnException
        from trytond.tools import is_instance_method
        from trytond.transaction import Transaction, TransactionError
        from trytond.worker import run_task

        if self._name in self._object.__rpc__:
            rpc = self._object.__rpc__[self._name]
        elif self._name in getattr(self._object, '_buttons', {}):
            rpc = RPC(readonly=False, instantiate=0)
        else:
            raise TypeError('%s is not callable' % self._name)

        extras = {}
        while True:
            with Transaction().start(self._config.database_name,
                    self._config.user, readonly=rpc.readonly,
                    **extras) as transaction:
                try:
                    (c_args, c_kwargs,
                        transaction.context, transaction.timestamp) \
                            = rpc.convert(self._object, *args, **kwargs)
                    if self._config.skip_warning:
                        transaction.context['_skip_warnings'] = True
                    meth = getattr(self._object, self._name)
                    if (rpc.instantiate is None
                            or not is_instance_method(
                                self._object, self._name)):
                        result = rpc.result(meth(*c_args, **c_kwargs))
                    else:
                        assert rpc.instantiate == 0
                        inst = c_args.pop(0)
                        if hasattr(inst, self._name):
                            result = rpc.result(
                                meth(inst, *c_args, **c_kwargs))
                        else:
                            result = [rpc.result(meth(i, *c_args, **c_kwargs))
                                for i in inst]
                except TransactionError as e:
                    transaction.rollback()
                    e.fix(extras)
                    continue
                except RPCReturnException as e:
                    transaction.rollback()
                    transaction.tasks.clear()
                    result = e.result()
                transaction.commit()
            break
        while transaction.tasks:
            task_id = transaction.tasks.pop()
            run_task(self._config.database_name, task_id)
        return result


class TrytondProxy(object):
    'Proxy for function call for trytond'

    def __init__(self, name, config, type='model'):
        super().__init__()
        self._config = config
        self._object = config.pool.get(name, type=type)
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return _TrytondMethod(name, self._object, self._config)


class TrytondConfig(Config):
    'Configuration for trytond'

    def __init__(self, database=None, user='admin', config_file=None):
        super().__init__()
        if not database:
            database = os.environ.get('TRYTOND_DATABASE_URI')
        elif (os.environ.get('TRYTOND_DATABASE_URI')
                and not urllib.parse.urlparse(database).scheme):
            url = urllib.parse.urlparse(os.environ['TRYTOND_DATABASE_URI'])
            os.environ['TRYTOND_DATABASE_URI'] = urllib.parse.urlunparse(
                url._replace(path=database))
        else:
            os.environ['TRYTOND_DATABASE_URI'] = database
        if not config_file:
            config_file = os.environ.get('TRYTOND_CONFIG')
        import trytond.config as config
        config.update_etc(config_file)
        from trytond.pool import Pool
        from trytond.transaction import Transaction
        self.database = database
        database_name = None
        if database:
            uri = urllib.parse.urlparse(database)
            database_name = uri.path.strip('/')
        if not database_name:
            database_name = os.environ['DB_NAME']
        self.database_name = database_name
        self._user = user
        self.config_file = config_file
        self.skip_warning = False

        Pool.start()
        self.pool = Pool(database_name)
        self.pool.init()

        with Transaction().start(self.database_name, 0) as transaction:
            User = self.pool.get('res.user')
            transaction.context = self.context
            with transaction.set_context(active_test=False):
                self.user = User.search([
                    ('login', '=', user),
                    ], limit=1)[0].id
            with transaction.set_user(self.user):
                self._context = User.get_preferences(context_only=True)
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return ("proteus.config.TrytondConfig"
            "(%s, %s, config_file=%s)"
            % (repr(self.database), repr(self._user), repr(self.config_file)))
    __repr__.__doc__ = object.__repr__.__doc__

    def __eq__(self, other):
        if not isinstance(other, TrytondConfig):
            raise NotImplementedError
        return (self.database_name == other.database_name
            and self._user == other._user
            and self.database == other.database
            and self.config_file == other.config_file)

    def __hash__(self):
        return hash((self.database_name, self._user,
            self.database, self.config_file))

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


def set_trytond(database=None, user='admin',
        config_file=None):
    'Set trytond package as backend'
    _CONFIG.current = TrytondConfig(database, user, config_file=config_file)
    return _CONFIG.current


class XmlrpcProxy(object):
    'Proxy for function call for XML-RPC'

    def __init__(self, name, config, type='model'):
        super().__init__()
        self._config = config
        self._object = getattr(config.server, '%s.%s' % (type, name))
    __init__.__doc__ = object.__init__.__doc__

    def __getattr__(self, name):
        'Return attribute value'
        return getattr(self._object, name)


class XmlrpcConfig(Config):
    'Configuration for XML-RPC'

    def __init__(self, url, **kwargs):
        super().__init__()
        self.url = url
        self.server = xmlrpc.client.ServerProxy(
            url, allow_none=True, use_builtin_types=True, **kwargs)
        # TODO add user
        self.user = None
        self._context = self.server.model.res.user.get_preferences(True, {})
    __init__.__doc__ = object.__init__.__doc__

    def __repr__(self):
        return "proteus.config.XmlrpcConfig(%s)" % repr(self.url)
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


def set_xmlrpc(url, **kwargs):
    '''
    Set XML-RPC as backend.
    It pass the keyword arguments received to xmlrpclib.ServerProxy()
    '''
    _CONFIG.current = XmlrpcConfig(url, **kwargs)
    return _CONFIG.current


@contextmanager
def set_xmlrpc_session(
        url, username, password=None, parameters=None, **kwargs):
    """
    Set XML-RPC as backend using session.
    """
    if parameters is None:
        parameters = {}
    else:
        parameters = parameters.copy()
    if password:
        parameters['password'] = password
    server = xmlrpc.client.ServerProxy(
        url, allow_none=True, use_builtin_types=True, **kwargs)
    session = server.common.db.login(username, parameters)
    session = ':'.join(map(str, [username] + session))
    auth = base64.encodebytes(session.encode('utf-8')).decode('ascii')
    auth = ''.join(auth.split())  # get rid of whitespace
    kwargs.setdefault('headers', []).append(
        ('Authorization', 'Session ' + auth))
    config = set_xmlrpc(url, **kwargs)
    yield config
    config.server.common.db.logout()


def get_config():
    return _CONFIG.current
