# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import xmlrpclib
import json
import ssl
import httplib
from decimal import Decimal
import datetime
import socket
import gzip
import StringIO
import hashlib
import base64
import threading
import errno
from functools import partial
from contextlib import contextmanager
import string

__all__ = ["ResponseError", "Fault", "ProtocolError", "Transport",
    "ServerProxy", "ServerPool"]
CONNECT_TIMEOUT = 5
DEFAULT_TIMEOUT = None


class ResponseError(xmlrpclib.ResponseError):
    pass


class Fault(xmlrpclib.Fault):

    def __init__(self, faultCode, faultString='', **extra):
        super(Fault, self).__init__(faultCode, faultString, **extra)
        self.args = faultString

    def __repr__(self):
        return (
            "<Fault %s: %s>" %
            (repr(self.faultCode), repr(self.faultString))
            )


class ProtocolError(xmlrpclib.ProtocolError):
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
            cast = bytearray if bytes == str else bytes
            return cast(base64.decodestring(dct['base64']))
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
        elif isinstance(obj, (bytes, bytearray)):
            return {'__class__': 'bytes',
                'base64': base64.encodestring(obj),
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
        self.data.append(data)

    def close(self):
        return json.loads(''.join(self.data), object_hook=object_hook)


class Transport(xmlrpclib.Transport, xmlrpclib.SafeTransport):

    accept_gzip_encoding = True
    encode_threshold = 1400  # common MTU

    def __init__(self, fingerprints=None, ca_certs=None, session=None):
        xmlrpclib.Transport.__init__(self)
        self._connection = (None, None)
        self.__fingerprints = fingerprints
        self.__ca_certs = ca_certs
        self.session = session

    def getparser(self):
        target = JSONUnmarshaller()
        parser = JSONParser(target)
        return parser, target

    def get_host_info(self, host):
        host, extra_headers, x509 = xmlrpclib.Transport.get_host_info(
            self, host)
        if extra_headers is None:
            extra_headers = []
        if self.session:
            auth = base64.encodestring(self.session)
            auth = string.join(string.split(auth), "")  # get rid of whitespace
            extra_headers.append(
                ('Authorization', 'Session ' + auth),
                )
        extra_headers.append(('Connection', 'keep-alive'))
        return host, extra_headers, x509

    def send_content(self, connection, request_body):
        connection.putheader("Content-Type", "application/json")
        if (self.encode_threshold is not None and
                self.encode_threshold < len(request_body) and
                gzip):
            connection.putheader("Content-Encoding", "gzip")
            buffer = StringIO.StringIO()
            output = gzip.GzipFile(mode='wb', fileobj=buffer)
            output.write(request_body)
            output.close()
            buffer.seek(0)
            request_body = buffer.getvalue()
        connection.putheader("Content-Length", str(len(request_body)))
        connection.endheaders()
        if request_body:
            connection.send(request_body)

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        host, self._extra_headers, x509 = self.get_host_info(host)

        ssl_ctx = ssl.create_default_context(cafile=self.__ca_certs)

        class HTTPSConnection(httplib.HTTPSConnection):

            def connect(self):
                sock = socket.create_connection((self.host, self.port),
                    self.timeout)
                if self._tunnel_host:
                    self.sock = sock
                    self._tunnel()
                self.sock = ssl_ctx.wrap_socket(
                    sock, server_hostname=self.host)

        def http_connection():
            self._connection = host, httplib.HTTPConnection(host,
                timeout=CONNECT_TIMEOUT)
            self._connection[1].connect()
            sock = self._connection[1].sock
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        def https_connection(allow_http=False):
            self._connection = host, HTTPSConnection(host,
                timeout=CONNECT_TIMEOUT)
            try:
                self._connection[1].connect()
                sock = self._connection[1].sock
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                try:
                    peercert = sock.getpeercert(True)
                except socket.error:
                    peercert = None

                def format_hash(value):
                    return reduce(lambda x, y: x + y[1].upper() +
                        ((y[0] % 2 and y[0] + 1 < len(value)) and ':' or ''),
                        enumerate(value), '')
                return format_hash(hashlib.sha1(peercert).hexdigest())
            except ssl.SSLError:
                if allow_http:
                    http_connection()
                else:
                    raise

        fingerprint = ''
        if self.__fingerprints is not None and host in self.__fingerprints:
            if self.__fingerprints[host]:
                fingerprint = https_connection()
            else:
                http_connection()
        else:
            fingerprint = https_connection(allow_http=True)

        if self.__fingerprints is not None:
            self.__fingerprints[host] = fingerprint
        self._connection[1].timeout = DEFAULT_TIMEOUT
        self._connection[1].sock.settimeout(DEFAULT_TIMEOUT)
        return self._connection[1]


class ServerProxy(xmlrpclib.ServerProxy):
    __id = 0

    def __init__(self, host, port, database='', verbose=0,
            fingerprints=None, ca_certs=None, session=None):
        self.__host = '%s:%s' % (host, port)
        if database:
            self.__handler = '/%s/' % database
        else:
            self.__handler = '/'
        self.__transport = Transport(fingerprints, ca_certs, session)
        self.__verbose = verbose

    def __request(self, methodname, params):
        self.__id += 1
        id_ = self.__id
        request = json.dumps({
                'id': id_,
                'method': methodname,
                'params': params,
                }, cls=JSONEncoder, separators=(',', ':'))

        try:
            try:
                response = self.__transport.request(
                    self.__host,
                    self.__handler,
                    request,
                    verbose=self.__verbose
                    )
            except (socket.error, httplib.HTTPException), v:
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
        except xmlrpclib.ProtocolError, e:
            raise Fault(str(e.errcode), e.errmsg)
        except:
            self.__transport.close()
            raise

        if response['id'] != id_:
            raise ResponseError('Invalid response id (%s) excpected %s' %
                (response['id'], id_))
        if response.get('error'):
            raise Fault(*response['error'])
        return response['result']

    def close(self):
        self.__transport.close()

    @property
    def ssl(self):
        return isinstance(self.__transport.make_connection(self.__host),
            httplib.HTTPSConnection)


class ServerPool(object):
    keep_max = 4

    def __init__(self, *args, **kwargs):
        self.ServerProxy = partial(ServerProxy, *args, **kwargs)
        self._lock = threading.Lock()
        self._pool = []
        self._used = {}
        self.session = None

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
            for conn in self._pool + self._used.values():
                conn.close()
            self._pool = []
            self._used.clear()

    @property
    def ssl(self):
        for conn in self._pool + self._used.values():
            return conn.ssl
        return False

    @contextmanager
    def __call__(self):
        conn = self.getconn()
        yield conn
        self.putconn(conn)
