#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.dispatcher import dispatch
from trytond.config import CONFIG
from trytond.protocols.common import daemon, RegisterHandlerMixin
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
from trytond import security
import SimpleXMLRPCServer
import SocketServer
import xmlrpclib
import traceback
import socket
import sys
import base64
import datetime
from types import DictType

# convert decimal to float before marshalling:
from decimal import Decimal


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
        'microsecond': value.microsecond,
        }
    self.dump_struct(value, write)

xmlrpclib.Marshaller.dispatch[Decimal] = dump_decimal
xmlrpclib.Marshaller.dispatch[type(None)] = \
        lambda self, value, write: write("<value><nil/></value>")
xmlrpclib.Marshaller.dispatch[datetime.date] = dump_date
xmlrpclib.Marshaller.dispatch[datetime.time] = dump_time
xmlrpclib.Marshaller.dispatch[buffer] = dump_buffer


def dump_struct(self, value, write, escape=xmlrpclib.escape):
    converted_value = {}
    for k, v in value.items():
        if type(k) in (int, long):
            k = str(int(k))
        elif type(k) == float:
            k = repr(k)
        converted_value[k] = v
    return self.dump_struct(converted_value, write, escape=escape)

xmlrpclib.Marshaller.dispatch[DictType] = dump_struct


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
            dct = datetime.time(dct['hour'], dct['minute'], dct['second'],
                dct['microsecond'])
        elif dct['__class__'] == 'Decimal':
            dct = Decimal(dct['decimal'])
    self._stack[mark:] = [dct]
    self._value = 0

xmlrpclib.Unmarshaller.dispatch['struct'] = end_struct


def _end_dateTime(self, data):
    value = xmlrpclib.DateTime()
    value.decode(data)
    value = xmlrpclib._datetime_type(data)
    self.append(value)
xmlrpclib.Unmarshaller.dispatch["dateTime.iso8601"] = _end_dateTime


class GenericXMLRPCRequestHandler:

    def _dispatch(self, method, params):
        host, port = self.client_address[:2]
        database_name = self.path[1:]
        user = self.tryton['user']
        session = self.tryton['session']
        try:
            try:
                method_list = method.split('.')
                object_type = method_list[0]
                object_name = '.'.join(method_list[1:-1])
                method = method_list[-1]
                if object_type == 'system' and method == 'getCapabilities':
                    return {
                        'introspect': {
                            'specUrl': ('http://xmlrpc-c.sourceforge.net/'
                                'xmlrpc-c/introspection.html'),
                            'specVersion': 1,
                        },
                    }
                return dispatch(host, port, 'XML-RPC', database_name, user,
                        session, object_type, object_name, method, *params)
            except (NotLogged, ConcurrencyException), exception:
                raise xmlrpclib.Fault(exception.code,
                    '\n'.join(exception.args))
            except (UserError, UserWarning), exception:
                error, description = exception.args
                raise xmlrpclib.Fault(exception.code,
                    '\n'.join((error,) + description))
            except Exception:
                tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
                for path in sys.path:
                    tb_s = tb_s.replace(path, '')
                if CONFIG['debug_mode']:
                    import pdb
                    traceb = sys.exc_info()[2]
                    pdb.post_mortem(traceb)
                raise xmlrpclib.Fault(255, str(sys.exc_value) + '\n' + tb_s)
        finally:
            security.logout(database_name, user, session)


class SimpleXMLRPCRequestHandler(RegisterHandlerMixin,
        GenericXMLRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    protocol_version = "HTTP/1.1"
    rpc_paths = None
    encode_threshold = 1400  # common MTU

    def parse_request(self):
        res = SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.parse_request(self)
        if not res:
            return res
        database_name = self.path[1:]
        if not database_name:
            self.tryton = {'user': None, 'session': None}
            return res
        try:
            method, up64 = self.headers['Authorization'].split(None, 1)
            if method.strip().lower() == 'basic':
                user, password = base64.decodestring(up64).split(':', 1)
                user_id, session = security.login(database_name, user,
                        password)
                self.tryton = {'user': user_id, 'session': session}
                return res
        except Exception:
            pass
        self.send_error(401, 'Unauthorized')
        self.send_header("WWW-Authenticate", 'Basic realm="Tryton"')
        return False


class SecureXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def setup(self):
        self.request = SSLSocket(self.request)
        SimpleXMLRPCRequestHandler.setup(self)


class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
        SimpleXMLRPCServer.SimpleXMLRPCServer):
    timeout = 1
    daemon_threads = True

    def __init__(self, server_address, HandlerClass, logRequests=1):
        self.handlers = set()
        SimpleXMLRPCServer.SimpleXMLRPCServer.__init__(self, server_address,
            HandlerClass, logRequests)

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET,
            socket.SO_KEEPALIVE, 1)
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_bind(self)

    def server_close(self):
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_close(self)
        for handler in self.handlers.copy():
            self.shutdown_request(handler.request)


class SimpleThreadedXMLRPCServer6(SimpleThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class SecureThreadedXMLRPCServer(SimpleThreadedXMLRPCServer):

    def __init__(self, server_address, HandlerClass, logRequests=1):
        SimpleThreadedXMLRPCServer.__init__(self, server_address, HandlerClass,
                logRequests)
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.server_bind()
        self.server_activate()


class SecureThreadedXMLRPCServer6(SecureThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class XMLRPCDaemon(daemon):

    def __init__(self, interface, port, secure=False):
        daemon.__init__(self, interface, port, secure, name='XMLRPCDaemon')
        if self.secure:
            handler_class = SecureXMLRPCRequestHandler
            server_class = SecureThreadedXMLRPCServer
            if self.ipv6:
                server_class = SecureThreadedXMLRPCServer6
        else:
            handler_class = SimpleXMLRPCRequestHandler
            server_class = SimpleThreadedXMLRPCServer
            if self.ipv6:
                server_class = SimpleThreadedXMLRPCServer6
        self.server = server_class((interface, port), handler_class, 0)
