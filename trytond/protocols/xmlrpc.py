#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.dispatcher import dispatch
from trytond.config import CONFIG
from trytond.protocols.datatype import Float
from trytond import security
import SimpleXMLRPCServer
import SocketServer
import xmlrpclib
import threading
import traceback
import socket
import sys
import os
import gzip
import StringIO
import base64
import datetime

# convert decimal to float before marshalling:
from decimal import Decimal
xmlrpclib.Marshaller.dispatch[Decimal] = \
        lambda self, value, write: self.dump_double(float(value), write)
xmlrpclib.Marshaller.dispatch[type(None)] = \
        lambda self, value, write: self.dump_bool(bool(value), write)
xmlrpclib.Marshaller.dispatch[datetime.date] = \
        lambda self, value, write: self.dump_datetime(
                datetime.datetime.combine(value, datetime.time()), write)

def _end_double(self, data):
    self.append(Float(data))
    self._value = 0
xmlrpclib.Unmarshaller.dispatch["double"] = _end_double
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
                            'specUrl': 'http://xmlrpc-c.sourceforge.net/' \
                                    'xmlrpc-c/introspection.html',
                            'specVersion': 1,
                        },
                    }
                return dispatch(host, port, 'XML-RPC', database_name, user,
                        session, object_type, object_name, method, *params)
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
        finally:
            security.logout(database_name, user, session)


class SimpleXMLRPCRequestHandler(GenericXMLRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = None
    encode_threshold = 1400 # common MTU

    def parse_request(self):
        res = SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.parse_request(self)
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
        except:
            pass
        self.send_error(401, 'Unauthorized')
        self.send_header("WWW-Authenticate", 'Basic realm="Tryton"')
        return False

    # Copy from SimpleXMLRPCServer.py with gzip encoding added
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the server's _dispatch method for handling.
        """

        # Check that the path is legal
        if not self.is_rpc_path_valid():
            self.report_404()
            return

        try:
            # Get arguments by reading body of request.
            # We read this in chunks to avoid straining
            # socket.read(); around the 10 or 15Mb mark, some platforms
            # begin to have problems (bug #792570).
            max_chunk_size = 10*1024*1024
            size_remaining = int(self.headers["content-length"])
            L = []
            while size_remaining:
                chunk_size = min(size_remaining, max_chunk_size)
                L.append(self.rfile.read(chunk_size))
                size_remaining -= len(L[-1])
            data = ''.join(L)

            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            response = self.server._marshaled_dispatch(
                    data, getattr(self, '_dispatch', None)
                )
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")

            # Handle gzip encoding
            if 'gzip' in self.headers.get('Accept-Encoding', '').split(',') \
                    and len(response) > self.encode_threshold:
                buffer = StringIO.StringIO()
                output = gzip.GzipFile(mode='wb', fileobj=buffer)
                output.write(response)
                output.close()
                buffer.seek(0)
                response = buffer.getvalue()
                self.send_header('Content-Encoding', 'gzip')

            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown(1)


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


class XMLRPCDaemon(threading.Thread):

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
