# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import datetime
import errno
import gettext
import hashlib
import http.client
import json
import logging
import socket
import ssl
import threading
import xmlrpc.client
from contextlib import contextmanager
from decimal import Decimal
from functools import partial, reduce
from urllib.parse import quote, urljoin

from .cache import CacheDict
from .config import CONFIG

__all__ = ["ResponseError", "Fault", "ProtocolError", "Transport",
    "ServerProxy", "ServerPool"]
CONNECT_TIMEOUT = 5
DEFAULT_TIMEOUT = None
logger = logging.getLogger(__name__)
_ = gettext.gettext


def deepcopy(obj):
    """Recursively copy python mutable datastructures"""
    if isinstance(obj, (list, tuple)):
        return [deepcopy(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: deepcopy(v) for k, v in obj.items()}
    else:
        return obj


class ResponseError(xmlrpc.client.ResponseError):
    pass


class Fault(xmlrpc.client.Fault):

    def __init__(self, faultCode, faultString='', **extra):
        super(Fault, self).__init__(faultCode, faultString, **extra)
        self.args = faultString

    def __str__(self):
        return str(self.faultCode)


class ProtocolError(xmlrpc.client.ProtocolError):
    pass


def object_hook(dct):
    if '__class__' in dct:
        if dct['__class__'] == 'datetime':
            return datetime.datetime(dct['year'], dct['month'], dct['day'],
                dct['hour'], dct['minute'], dct['second'], dct['microsecond'])
        elif dct['__class__'] == 'date':
            return datetime.date(dct['year'], dct['month'], dct['day'])
        elif dct['__class__'] == 'time':
            return datetime.time(dct['hour'], dct['minute'], dct['second'],
                dct['microsecond'])
        elif dct['__class__'] == 'timedelta':
            return datetime.timedelta(seconds=dct['seconds'])
        elif dct['__class__'] == 'bytes':
            return base64.decodebytes(dct['base64'].encode('utf-8'))
        elif dct['__class__'] == 'Decimal':
            return Decimal(dct['decimal'])
    return dct


class JSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.date):
            if isinstance(obj, datetime.datetime):
                return {'__class__': 'datetime',
                        'year': obj.year,
                        'month': obj.month,
                        'day': obj.day,
                        'hour': obj.hour,
                        'minute': obj.minute,
                        'second': obj.second,
                        'microsecond': obj.microsecond,
                        }
            return {'__class__': 'date',
                    'year': obj.year,
                    'month': obj.month,
                    'day': obj.day,
                    }
        elif isinstance(obj, datetime.time):
            return {'__class__': 'time',
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
                }
        elif isinstance(obj, datetime.timedelta):
            return {'__class__': 'timedelta',
                'seconds': obj.total_seconds(),
                }
        elif isinstance(obj, bytes):
            return {'__class__': 'bytes',
                'base64': base64.encodebytes(obj).decode('utf-8'),
                }
        elif isinstance(obj, Decimal):
            return {'__class__': 'Decimal',
                'decimal': str(obj),
                }
        return super(JSONEncoder, self).default(obj)


class JSONParser(object):

    def __init__(self, target):
        self.__targer = target

    def feed(self, data):
        self.__targer.feed(data)

    def close(self):
        pass


class JSONUnmarshaller(object):
    def __init__(self):
        self.data = []

    def feed(self, data):
        self.data.append(data.decode('utf-8'))

    def close(self):
        return json.loads(''.join(self.data), object_hook=object_hook)


class Transport(xmlrpc.client.SafeTransport):

    accept_gzip_encoding = True

    def __init__(
            self, fingerprints=None, ca_certs=None, session=None):
        xmlrpc.client.Transport.__init__(self)
        self._connection = (None, None)
        self.__fingerprints = fingerprints
        self.__ca_certs = ca_certs
        self.session = session

    def getparser(self):
        target = JSONUnmarshaller()
        parser = JSONParser(target)
        return parser, target

    def parse_response(self, response):
        cache = None
        if hasattr(response, 'getheader'):
            cache = int(response.getheader('X-Tryton-Cache', 0))
        response = super().parse_response(response)
        if cache:
            try:
                response['cache'] = int(cache)
            except ValueError:
                pass
        return response

    def get_host_info(self, host):
        host, extra_headers, x509 = xmlrpc.client.Transport.get_host_info(
            self, host)
        if extra_headers is None:
            extra_headers = []
        if self.session:
            auth = base64.encodebytes(
                self.session.encode('utf-8')).decode('ascii')
            auth = ''.join(auth.split())  # get rid of whitespace
            extra_headers.append(
                ('Authorization', 'Session ' + auth),
                )
        extra_headers.append(('Connection', 'keep-alive'))
        return host, extra_headers, x509

    def send_headers(self, connection, headers):
        for key, val in headers:
            if key == 'Content-Type':
                val = 'application/json'
            connection.putheader(key, val)

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        chost, self._extra_headers, x509 = self.get_host_info(host)

        ssl_ctx = ssl.create_default_context(cafile=self.__ca_certs)

        def http_connection():
            connection = http.client.HTTPConnection(
                chost, timeout=CONNECT_TIMEOUT)
            self._connection = host, connection
            connection.connect()
            sock = connection.sock
            if sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            return connection

        def https_connection(allow_http=False):
            connection = http.client.HTTPSConnection(
                chost, timeout=CONNECT_TIMEOUT, context=ssl_ctx)
            self._connection = host, connection
            try:
                connection.connect()
                sock = connection.sock
                if sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    try:
                        peercert = sock.getpeercert(True)
                    except socket.error:
                        peercert = None

                def format_hash(value):
                    return reduce(lambda x, y: x + y[1].upper()
                        + ((y[0] % 2 and y[0] + 1 < len(value)) and ':' or ''),
                        enumerate(value), '')
                return connection, format_hash(
                    hashlib.sha1(peercert).hexdigest())
            except (socket.error, ssl.SSLError, ssl.CertificateError):
                if allow_http:
                    return http_connection(), None
                else:
                    raise

        fingerprint = ''
        if (self.__fingerprints is not None
                and self.__fingerprints.exists(chost)):
            if self.__fingerprints.get(chost):
                connection, fingerprint = https_connection()
            else:
                connection = http_connection()
        else:
            connection, fingerprint = https_connection(allow_http=True)

        if self.__fingerprints is not None:
            self.__fingerprints.set(chost, fingerprint)
        connection.timeout = DEFAULT_TIMEOUT
        sock = connection.sock
        if sock:
            sock.settimeout(DEFAULT_TIMEOUT)
        return connection

    @property
    def encode_threshold(self):
        if self.session:
            return 1400  # common MTU


class ServerProxy(xmlrpc.client.ServerProxy):
    __id = 0

    def __init__(self, host, port, database='', verbose=0,
            fingerprints=None, ca_certs=None, session=None, cache=None):
        self.__host = '%s:%s' % (host, port)
        if database:
            database = quote(database)
            self.__handler = '/%s/' % database
        else:
            self.__handler = '/'
        self.__transport = Transport(fingerprints, ca_certs, session)
        self.__verbose = verbose
        self.__cache = cache

    def __request(self, methodname, params):
        dumper = partial(json.dumps, cls=JSONEncoder, separators=(',', ':'))
        self.__id += 1
        id_ = self.__id
        if self.__cache and self.__cache.cached(methodname):
            try:
                return self.__cache.get(methodname, dumper(params))
            except KeyError:
                pass
        request = dumper({
                'id': id_,
                'method': methodname,
                'params': params,
                }).encode('utf-8')

        try:
            try:
                response = self.__transport.request(
                    self.__host,
                    self.__handler,
                    request,
                    verbose=self.__verbose
                    )
            except (socket.error, http.client.HTTPException) as v:
                if (isinstance(v, socket.error)
                        and v.args[0] == errno.EPIPE):
                    raise
                # try one more time
                self.__transport.close()
                response = self.__transport.request(
                    self.__host,
                    self.__handler,
                    request,
                    verbose=self.__verbose
                    )
        except xmlrpc.client.ProtocolError as e:
            raise Fault(str(e.errcode), e.errmsg)
        except Exception:
            self.__transport.close()
            raise
        if response['id'] != id_:
            raise ResponseError(
                _("Invalid response id (%s) expected %s") %
                (response['id'], id_))
        if response.get('error'):
            raise Fault(*response['error'])
        if self.__cache and response.get('cache'):
            self.__cache.set(
                methodname, dumper(params), response['cache'],
                response['result'])
        return response['result']

    def close(self):
        self.__transport.close()

    @property
    def ssl(self):
        return isinstance(self.__transport.make_connection(self.__host),
            http.client.HTTPSConnection)

    @property
    def url(self):
        scheme = 'https' if self.ssl else 'http'
        return urljoin(scheme + '://' + self.__host, self.__handler)


class ServerPool(object):
    keep_max = 4
    _cache = None

    def __init__(self, host, port, database, *args, **kwargs):
        if kwargs.get('cache'):
            self._cache = kwargs['cache'] = _Cache()
        self.ServerProxy = partial(
            ServerProxy, host, port, database, *args, **kwargs)

        self._host = host
        self._port = port
        self._database = database

        self._lock = threading.Lock()
        self._pool = []
        self._used = {}
        self.session = kwargs.get('session')

    def getconn(self):
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
            else:
                conn = self.ServerProxy()
            self._used[id(conn)] = conn
            return conn

    def putconn(self, conn):
        with self._lock:
            self._pool.append(conn)
            del self._used[id(conn)]

            # Remove oldest connections
            while len(self._pool) > self.keep_max:
                conn = self._pool.pop()
                conn.close()

    def close(self):
        with self._lock:
            for conn in self._pool + list(self._used.values()):
                conn.close()
            self._pool = []
            self._used.clear()

    @property
    def ssl(self):
        for conn in self._pool + list(self._used.values()):
            return conn.ssl
        return None

    @property
    def url(self):
        for conn in self._pool + list(self._used.values()):
            return conn.url

    @contextmanager
    def __call__(self):
        conn = self.getconn()
        yield conn
        self.putconn(conn)

    def clear_cache(self, prefix=None):
        if self._cache:
            self._cache.clear(prefix)


class _Cache:

    def __init__(self):
        cache_size = CONFIG['rpc.cache_size']
        self.store = CacheDict(
            cache_len=cache_size,
            default_factory=lambda: CacheDict(cache_len=cache_size))

    def cached(self, prefix):
        return prefix in self.store

    def set(self, prefix, key, expire, value):
        if isinstance(expire, (int, float)):
            expire = datetime.timedelta(seconds=expire)
        if isinstance(expire, datetime.timedelta):
            expire = datetime.datetime.now() + expire
        self.store[prefix][key] = (expire, deepcopy(value))

    def get(self, prefix, key):
        now = datetime.datetime.now()
        try:
            expire, value = self.store[prefix][key]
        except ValueError:
            raise KeyError
        if expire < now:
            self.store.pop(key)
            raise KeyError
        logger.info('(cached) %s %s', prefix, key)
        return deepcopy(value)

    def clear(self, prefix=None):
        if prefix:
            self.store[prefix].clear()
        else:
            self.store.clear()
