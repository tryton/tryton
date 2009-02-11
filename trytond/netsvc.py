#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import time
import threading
import SimpleXMLRPCServer, signal, sys, xmlrpclib
import SocketServer
import socket
import logging
import os
from pysocket import PySocket
import traceback
import select
import BaseHTTPServer

_SERVICE = {}
_GROUP = {}
_RES = {}

LOG_DEBUG = 'debug'
LOG_INFO = 'info'
LOG_WARNING = 'warn'
LOG_ERROR = 'error'
LOG_CRITICAL = 'critical'

from config import CONFIG

# convert decimal to float before marshalling:
from decimal import Decimal
xmlrpclib.Marshaller.dispatch[Decimal] = \
    lambda self, value, write: self.dump_long(float(value), write)


class SSLSocket(object):

    def __init__(self, socket):
        if not hasattr(socket, 'sock_shutdown'):
            from OpenSSL import SSL
            ctx = SSL.Context(SSL.SSLv23_METHOD)
            ctx.use_privatekey_file(CONFIG['privatekey'])
            ctx.use_certificate_file(CONFIG['certificate'])
            self.socket = SSL.Connection(ctx, socket)
        else:
            self.socket = socket

    def shutdown(self, how):
        return self.socket.sock_shutdown(how)

    def __getattr__(self, name):
        if name == 'shutdown':
            return self.shutdown
        return getattr(self.socket, name)


class Service(object):
    _serviceEndPointID = 0

    def __init__(self, name=None):
        if name is None:
            return
        _SERVICE[name] = self
        self.__name = name
        self.method = {}
        self.exportedmethods = None
        self._response_process = None
        self._response_process_id = None

    def join_group(self, name):
        if not name in _GROUP:
            _GROUP[name] = {}
        _GROUP[name][self.__name] = self

    def export_method(self, method):
        if callable(method):
            self.method[method.__name__] = method


class LocalService(Service):

    def __init__(self, name):
        super(LocalService, self).__init__()
        self.__name = name
        service = _SERVICE[name]
        self.service = service
        for method in service.method:
            setattr(self, method, service.method[method])


class ServiceUnavailable(Exception):
    pass

def service_exist(name):
    return (name in _SERVICE) and bool(_SERVICE[name])


class RpcGateway(object):

    def __init__(self, name):
        self.name = name


class Dispatcher(object):

    def __init__(self):
        pass

    def monitor(self, sig):
        pass

    def run(self):
        pass


class XmlRpc(object):


    class RpcGateway(object):

        def __init__(self, name):
            self.name = name


#-- XMLRPC Handler

class GenericXMLRPCRequestHandler:

    def _dispatch(self, method, params):
        host, port = self.client_address[:2]
        logging.getLogger('web-service').info(
            'connection from %s:%d' % (host, port))
        try:
            name = self.path.split("/")[-1]
            service = LocalService(name)
            meth = getattr(service, method)
            res = meth(*params)
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
            raise xmlrpclib.Fault(str(sys.exc_value), tb_s)


class SimpleXMLRPCRequestHandler(GenericXMLRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = map(lambda s: '/xmlrpc/%s' % s, _SERVICE)


class SecureXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def setup(self):
        self.connection = SSLSocket(self.request)
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

#-- XMLRPC Server

class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
        SimpleXMLRPCServer.SimpleXMLRPCServer):

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_bind(self)


class SecureThreadedXMLRPCServer(SimpleThreadedXMLRPCServer):

    def __init__(self, server_address, HandlerClass, logRequests=1):
        SimpleThreadedXMLRPCServer.__init__(self, server_address, HandlerClass,
                logRequests)
        self.socket = SSLSocket(socket.socket(self.address_family,
                                              self.socket_type))
        self.server_bind()
        self.server_activate()


#-- HTPP Daemon

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

    def attach(self, path, gateway):
        pass

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.server.register_introspection_functions()

        self.running = True
        while self.running:
            self.server.handle_request()
        return True

        # If the server need to be run recursively
        #
        #signal.signal(signal.SIGALRM, self.my_handler)
        #signal.alarm(6)
        #while True:
        #    self.server.handle_request()
        #signal.alarm(0)          # Disable the alarm


class TinySocketClientThread(threading.Thread):
    def __init__(self, sock, threads, secure):
        threading.Thread.__init__(self)
        self.sock = sock
        self.threads = threads
        self.running = False
        self.secure = secure

    def run(self):
        self.running = True
        try:
            pysocket = PySocket(self.sock)
        except:
            self.sock.close()
            self.threads.remove(self)
            return False
        first = True
        timeout = 0
        while self.running:
            (rlist, wlist, xlist) = select.select([self.sock], [], [], 1)
            if not rlist:
                timeout += 1
                if timeout > 600:
                    break
                continue
            timeout = 0
            try:
                msg = pysocket.receive()
            except:
                pysocket.disconnect()
                self.threads.remove(self)
                return False
            if first:
                host, port = self.sock.getpeername()[:2]
                logging.getLogger('web-service').info(
                    'connection from %s:%d' % (host, port))
                first = False
            try:
                service = LocalService(msg[0])
                method = getattr(service, msg[1])
                res = method(*msg[2:])
                pysocket.send(res)
            except Exception, exception:
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
                    tback = sys.exc_info()[2]
                    pdb.post_mortem(tback)
                try:
                    pysocket.send(exception.args, exception=True, traceback=tb_s)
                except:
                    pysocket.disconnect()
                    self.threads.remove(self)
                    return False
        pysocket.disconnect()
        self.threads.remove(self)
        return True

    def stop(self):
        self.running = False


class TinySocketServerThread(threading.Thread):
    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.socket = None
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            except:
                pass
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if secure:
            self.socket = SSLSocket(self.socket)
        self.socket.bind((interface, port))
        self.socket.listen(5)
        self.threads = []
        self.secure = secure
        self.running = False

    def run(self):
        try:
            self.running = True
            while self.running:
                if not int(CONFIG['max_thread']) \
                        or len(self.threads) < int(CONFIG['max_thread']):
                    (clientsocket, address) = self.socket.accept()
                    c_thread = TinySocketClientThread(clientsocket, self.threads,
                            self.secure)
                    self.threads.append(c_thread)
                    c_thread.start()
        except:
            self.socket.close()
            return False

    def stop(self):
        self.running = False
        while len(self.threads):
            try:
                thread = self.threads[0]
                thread.stop()
                time.sleep(0.001) #sleep to let thread running
            except:
                pass
        try:
            if hasattr(socket, 'SHUT_RDWR'):
                self.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.socket.shutdown(2)
            self.socket.close()
        except:
            return False

#-- WebDAV server

class BaseThreadedHTTPServer(SocketServer.ThreadingMixIn,
        BaseHTTPServer.HTTPServer):

    max_children = CONFIG['max_thread']

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        BaseHTTPServer.HTTPServer.server_bind(self)


class SecureThreadedHTTPServer(BaseThreadedHTTPServer):

    def __init__(self, server_address, HandlerClass):
        BaseThreadedHTTPServer.__init__(self, server_address, HandlerClass)
        self.socket = SSLSocket(socket.socket(self.address_family,
                                              self.socket_type))
        self.server_bind()
        self.server_activate()


class WebDAVServerThread(threading.Thread):

    def __init__(self, interface, port, secure=False):
        from webdavsvc import WebDAVAuthRequestHandler, SecureWebDAVAuthRequestHandler, \
                TrytonDAVInterface
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
            handler_class = SecureWebDAVAuthRequestHandler
            server_class = SecureThreadedHTTPServer
            if ipv6:
                server_class = SecureThreadedHTTPServer6
        else:
            handler_class = WebDAVAuthRequestHandler
            server_class = BaseThreadedHTTPServer
            if ipv6:
                server_class = BaseThreadedHTTPServer6
        handler_class.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
        self.server = server_class((interface, port), handler_class)

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

#-- MixIn classes --

class IPv6MixIn(object):
    address_family = socket.AF_INET6

#--- IPv6 Servers

class BaseThreadedHTTPServer6(BaseThreadedHTTPServer, IPv6MixIn):
    pass
class SecureThreadedHTTPServer6(SecureThreadedHTTPServer, IPv6MixIn):
    pass
class SimpleThreadedXMLRPCServer6(SimpleThreadedXMLRPCServer, IPv6MixIn):
    pass

#--- Secure IPv6 Servers

class SecureThreadedXMLRPCServer6(SecureThreadedXMLRPCServer, IPv6MixIn):
    pass
class SecureThreadedHTTPServer6(SecureThreadedHTTPServer, IPv6MixIn):
    pass
