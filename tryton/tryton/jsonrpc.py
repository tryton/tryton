#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import xmlrpclib
try:
    import simplejson as json
except ImportError:
    import json
import ssl
import httplib
from decimal import Decimal
import datetime
import socket
import gzip
import StringIO
import hashlib
import sys
import base64

__all__ = ["ResponseError", "Fault", "ProtocolError", "Transport",
    "ServerProxy"]
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
                    dct['hour'], dct['minute'], dct['second'])
        elif dct['__class__'] == 'date':
            return datetime.date(dct['year'], dct['month'], dct['day'])
        elif dct['__class__'] == 'time':
            return datetime.time(dct['hour'], dct['minute'], dct['second'])
        elif dct['__class__'] == 'buffer':
            return buffer(base64.decodestring(dct['base64']))
        elif dct['__class__'] == 'Decimal':
            return Decimal(dct['decimal'])
    return dct


class JSONEncoder(json.JSONEncoder):

    def __init__(self, *args, **kwargs):
        super(JSONEncoder, self).__init__(*args, **kwargs)
        # Force to use our custom decimal with simplejson
        self.use_decimal = False

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
                }
        elif isinstance(obj, buffer):
            return {'__class__': 'buffer',
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
    data = ''

    def feed(self, data):
        self.data += data

    def close(self):
        return json.loads(self.data, object_hook=object_hook)


class Transport(xmlrpclib.Transport, xmlrpclib.SafeTransport):

    accept_gzip_encoding = True
    encode_threshold = 1400  # common MTU

    def __init__(self, fingerprints=None, ca_certs=None):
        xmlrpclib.Transport.__init__(self)
        self._connection = (None, None)
        self.__fingerprints = fingerprints
        self.__ca_certs = ca_certs

    def getparser(self):
        target = JSONUnmarshaller()
        parser = JSONParser(target)
        return parser, target

    def get_host_info(self, host):
        host, extra_headers, x509 = xmlrpclib.Transport.get_host_info(
            self, host)
        if extra_headers is None:
            extra_headers = []
        extra_headers.append(('Connection', 'keep-alive'))
        return host, extra_headers, x509

    def send_content(self, connection, request_body):
        connection.putheader("Content-Type", "text/json")
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
        host, extra_headers, x509 = self.get_host_info(host)

        ca_certs = self.__ca_certs
        cert_reqs = ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE

        class HTTPSConnection(httplib.HTTPSConnection):

            def connect(self):
                sock = socket.create_connection((self.host, self.port),
                    self.timeout)
                if self._tunnel_host:
                    self.sock = sock
                    self._tunnel()
                self.sock = ssl.wrap_socket(sock, self.key_file,
                    self.cert_file, ca_certs=ca_certs, cert_reqs=cert_reqs)

        def http_connection():
            self._connection = host, httplib.HTTPConnection(host,
                timeout=CONNECT_TIMEOUT)
            self._connection[1].connect()
            sock = self._connection[1].sock
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        def https_connection():
            self._connection = host, HTTPSConnection(host,
                timeout=CONNECT_TIMEOUT)
            try:
                self._connection[1].connect()
                sock = self._connection[1].sock
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
                http_connection()

        fingerprint = ''
        if self.__fingerprints is not None and host in self.__fingerprints:
            if self.__fingerprints[host]:
                fingerprint = https_connection()
            else:
                http_connection()
        else:
            fingerprint = https_connection()

        if self.__fingerprints is not None:
            if host in self.__fingerprints and self.__fingerprints[host]:
                if self.__fingerprints[host] != fingerprint:
                    self.close()
                    raise ssl.SSLError('BadFingerprint')
            else:
                self.__fingerprints[host] = fingerprint
        self._connection[1].timeout = DEFAULT_TIMEOUT
        self._connection[1].sock.settimeout(DEFAULT_TIMEOUT)
        return self._connection[1]

    if sys.version_info[:2] <= (2, 6):

        def request(self, host, handler, request_body, verbose=0):
            h = self.make_connection(host)
            if verbose:
                h.set_debuglevel(1)

            self.send_request(h, handler, request_body)
            self.send_host(h, host)
            self.send_user_agent(h)
            self.send_content(h, request_body)

            response = h.getresponse()

            if response.status != 200:
                raise ProtocolError(
                    host + handler,
                    response.status,
                    response.reason,
                    response.getheaders()
                    )

            self.verbose = verbose

            try:
                sock = h._conn.sock
            except AttributeError:
                sock = None

            if response.getheader("Content-Encoding", "") == "gzip":
                response = gzip.GzipFile(mode="rb",
                    fileobj=StringIO.StringIO(response.read()))
                sock = None

            return self._parse_response(response, sock)

        def send_request(self, connection, handler, request_body):
            xmlrpclib.Transport.send_request(self, connection, handler,
                request_body)
            connection.putheader("Accept-Encoding", "gzip")

        def close(self):
            if self._connection[1]:
                self._connection[1].close()
                self._connection = (None, None)


class ServerProxy(xmlrpclib.ServerProxy):
    __id = 0

    def __init__(self, host, port, database='', verbose=0,
            fingerprints=None, ca_certs=None):
        self.__host = '%s:%s' % (host, port)
        self.__handler = '/' + database
        self.__transport = Transport(fingerprints, ca_certs)
        self.__verbose = verbose

    def __request(self, methodname, params):
        self.__id += 1
        id_ = self.__id
        request = json.dumps({
                'id': id_,
                'method': methodname,
                'params': params,
                }, cls=JSONEncoder)

        try:
            response = self.__transport.request(
                self.__host,
                self.__handler,
                request,
                verbose=self.__verbose
                )
        except (socket.error, httplib.HTTPException), v:
            # trap  'Broken pipe'
            if isinstance(v, socket.error) and v.args[0] != 32:
                raise
            # try one more time
            self.__transport.close()
            response = self.__transport.request(
                self.__host,
                self.__handler,
                request,
                verbose=self.__verbose
                )
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
