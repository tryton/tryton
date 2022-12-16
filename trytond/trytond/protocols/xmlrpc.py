#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.dispatcher import dispatch
from trytond.config import CONFIG
import SimpleXMLRPCServer
import SocketServer
import xmlrpclib
import threading
import traceback
import socket
import sys
import os
from types import DictType

# convert decimal to float before marshalling:
from decimal import Decimal
xmlrpclib.Marshaller.dispatch[Decimal] = \
        lambda self, value, write: self.dump_double(float(value), write)
xmlrpclib.Marshaller.dispatch[type(None)] = \
        lambda self, value, write: self.dump_bool(bool(value), write)

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


class GenericXMLRPCRequestHandler:

    def _dispatch(self, method, params):
        host, port = self.client_address[:2]
        try:
            database_name = self.path[1:]
            method_list = method.split('.')
            object_type = method_list[0]
            object_name = '.'.join(method_list[1:-1])
            method = method_list[-1]
            if object_type == 'system' and method == 'getCapabilities':
                return {
                    'introspect': {
                        'specUrl': 'http://xmlrpc-c.sourceforge.net/' \
                                'xmlrpc-c/introspection.html',
                        'specVersion': 1,
                    },
                }
            if object_type == 'system':
                args = (host, port, 'XML-RPC', database_name, None, None,
                        object_type, None, method) + params
            else:
                args = (host, port, 'XML-RPC', database_name, params[0], params[1],
                        object_type, object_name, method) + params[2:]
            res = dispatch(*args)
            return res
        except:
            tb_s = ''
            for line in traceback.format_exception(*sys.exc_info()):
                try:
                    line = line.encode('utf-8', 'ignore')
                except:
                    continue
                tb_s += line
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            if CONFIG['debug_mode']:
                import pdb
                traceb = sys.exc_info()[2]
                pdb.post_mortem(traceb)
            raise xmlrpclib.Fault(1, str(sys.exc_value) + '\n' + tb_s)


class SimpleXMLRPCRequestHandler(GenericXMLRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = None


class SecureXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def setup(self):
        self.connection = SSLSocket(self.request)
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)


class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
        SimpleXMLRPCServer.SimpleXMLRPCServer):
    timeout = 1

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_bind(self)


class SimpleThreadedXMLRPCServer6(SimpleThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class SecureThreadedXMLRPCServer(SimpleThreadedXMLRPCServer):

    def __init__(self, server_address, HandlerClass, logRequests=1):
        SimpleThreadedXMLRPCServer.__init__(self, server_address, HandlerClass,
                logRequests)
        self.socket = SSLSocket(socket.socket(self.address_family,
            self.socket_type))
        self.server_bind()
        self.server_activate()


class SecureThreadedXMLRPCServer6(SecureThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class HttpDaemon(threading.Thread):

    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.secure = secure
        self.running = False
        ipv6 = False
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                ipv6 = True
            except:
                pass
        if secure:
            handler_class = SecureXMLRPCRequestHandler
            server_class = SecureThreadedXMLRPCServer
            if ipv6:
                server_class = SecureThreadedXMLRPCServer6
        else:
            handler_class = SimpleXMLRPCRequestHandler
            server_class = SimpleThreadedXMLRPCServer
            if ipv6:
                server_class = SimpleThreadedXMLRPCServer6
        self.server = server_class((interface, port), handler_class, 0)

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()
        return True
