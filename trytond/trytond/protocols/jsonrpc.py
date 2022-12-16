#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.dispatcher import dispatch
from trytond.config import config
from trytond.protocols.common import daemon, RegisterHandlerMixin
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
import SimpleXMLRPCServer
import SimpleHTTPServer
import SocketServer
import traceback
import socket
import sys
import os
try:
    import fcntl
except ImportError:
    fcntl = None
import posixpath
import urllib
import datetime
from decimal import Decimal
try:
    import simplejson as json
except ImportError:
    import json
import base64
import encodings
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class JSONDecoder(object):

    decoders = {}

    @classmethod
    def register(cls, klass, decoder):
        assert klass not in cls.decoders
        cls.decoders[klass] = decoder

    def __call__(self, dct):
        if dct.get('__class__') in self.decoders:
            return self.decoders[dct['__class__']](dct)
        return dct

JSONDecoder.register('datetime',
    lambda dct: datetime.datetime(dct['year'], dct['month'], dct['day'],
        dct['hour'], dct['minute'], dct['second'], dct['microsecond']))
JSONDecoder.register('date',
    lambda dct: datetime.date(dct['year'], dct['month'], dct['day']))
JSONDecoder.register('time',
    lambda dct: datetime.time(dct['hour'], dct['minute'], dct['second'],
        dct['microsecond']))
JSONDecoder.register('buffer', lambda dct:
    buffer(base64.decodestring(dct['base64'])))
JSONDecoder.register('Decimal', lambda dct: Decimal(dct['decimal']))


class JSONEncoder(json.JSONEncoder):

    serializers = {}

    def __init__(self, *args, **kwargs):
        super(JSONEncoder, self).__init__(*args, **kwargs)
        # Force to use our custom decimal with simplejson
        self.use_decimal = False

    @classmethod
    def register(cls, klass, encoder):
        assert klass not in cls.serializers
        cls.serializers[klass] = encoder

    def default(self, obj):
        marshaller = self.serializers.get(type(obj),
            super(JSONEncoder, self).default)
        return marshaller(obj)

JSONEncoder.register(datetime.datetime,
    lambda o: {
        '__class__': 'datetime',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(datetime.date,
    lambda o: {
        '__class__': 'date',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        })
JSONEncoder.register(datetime.time,
    lambda o: {
        '__class__': 'time',
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(buffer,
    lambda o: {
        '__class__': 'buffer',
        'base64': base64.encodestring(o),
        })
JSONEncoder.register(Decimal,
    lambda o: {
        '__class__': 'Decimal',
        'decimal': str(o),
        })


class SimpleJSONRPCDispatcher(SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """Mix-in class that dispatches JSON-RPC requests.

    This class is used to register JSON-RPC method handlers
    and then to dispatch them. There should never be any
    reason to instantiate this class directly.
    """

    def _marshaled_dispatch(self, data, dispatch_method=None, path=None):
        """Dispatches an JSON-RPC method from marshalled (JSON) data.

        JSON-RPC methods are dispatched from the marshalled (JSON) data
        using the _dispatch method and the result is returned as
        marshalled data. For backwards compatibility, a dispatch
        function can be provided as an argument (see comment in
        SimpleJSONRPCRequestHandler.do_POST) but overriding the
        existing method through subclassing is the prefered means
        of changing method dispatch behavior.
        """
        rawreq = json.loads(data, object_hook=JSONDecoder())

        req_id = rawreq.get('id', 0)
        method = rawreq['method']
        params = rawreq.get('params', [])

        response = {'id': req_id}

        try:
            #generate response
            if dispatch_method is not None:
                response['result'] = dispatch_method(method, params)
            else:
                response['result'] = self._dispatch(method, params)
        except (UserError, UserWarning, NotLogged,
                ConcurrencyException), exception:
            response['error'] = exception.args
        except Exception:
            tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            # report exception back to server
            response['error'] = (str(sys.exc_value), tb_s)

        return json.dumps(response, cls=JSONEncoder)


class GenericJSONRPCRequestHandler:

    def _dispatch(self, method, params):
        host, port = self.client_address[:2]
        database_name = self.path[1:]
        if database_name.startswith('sao/'):
            database_name = database_name[4:]
        method_list = method.split('.')
        object_type = method_list[0]
        object_name = '.'.join(method_list[1:-1])
        method = method_list[-1]
        args = (host, port, 'JSON-RPC', database_name, params[0], params[1],
                object_type, object_name, method) + tuple(params[2:])
        res = dispatch(*args)
        return res


class SimpleJSONRPCRequestHandler(RegisterHandlerMixin,
        GenericJSONRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler,
        SimpleHTTPServer.SimpleHTTPRequestHandler):
    """Simple JSON-RPC request handler class.

    Handles all HTTP POST requests and attempts to decode them as
    JSON-RPC requests.
    """
    protocol_version = "HTTP/1.1"
    rpc_paths = None
    encode_threshold = 1400  # common MTU

    def send_header(self, keyword, value):
        if keyword == 'Content-type' and value == 'text/xml':
            value = 'application/json-rpc'
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.send_header(self,
            keyword, value)

    def do_GET(self):
        if self.is_tryton_url(self.path):
            self.send_tryton_url(self.path)
            return
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):
        if self.is_tryton_url(self.path):
            self.send_tryton_url(self.path)
            return
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_HEAD(self)

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = config.get('jsonrpc', 'data')
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir):
                continue
            path = os.path.join(path, word)
        return path

    def is_tryton_url(self, path):
        words = path.split('/')
        try:
            return words[2] in ('model', 'wizard', 'report')
        except IndexError:
            return False

    def send_tryton_url(self, path):
        self.send_response(300)
        hostname = (config.get('jsonrpc', 'hostname')
            or unicode(socket.getfqdn(), 'utf8'))
        hostname = '.'.join(encodings.idna.ToASCII(part) for part in
            hostname.split('.'))
        values = {
            'hostname': hostname,
            'path': path,
            }
        content = StringIO()
        content.write('<html')
        content.write('<head>')
        content.write('<meta http-equiv="Refresh" '
            'content="0;url=tryton://%(hostname)s%(path)s"/>' % values)
        content.write('<title>Moved</title>')
        content.write('</head>')
        content.write('<body>')
        content.write('<h1>Moved</h1>')
        content.write('<p>This page has moved to '
            '<a href="tryton://%(hostname)s%(path)s">'
            'tryton://%(hostname)s%(path)s</a>.</p>' % values)
        content.write('</body>')
        content.write('</html>')
        length = content.tell()
        content.seek(0)
        self.send_header('Location', 'tryton://%(hostname)s%(path)s' % values)
        self.send_header('Content-type', 'text/html')
        self.send_header('Content-Length', str(length))
        self.end_headers()
        self.copyfile(content, self.wfile)
        content.close()

SimpleJSONRPCRequestHandler.extensions_map.update({
        '.svg': 'image/svg+xml',
        })


class SecureJSONRPCRequestHandler(SimpleJSONRPCRequestHandler):

    def setup(self):
        self.request = SSLSocket(self.request)
        SimpleJSONRPCRequestHandler.setup(self)


class SimpleJSONRPCServer(SocketServer.TCPServer,
        SimpleJSONRPCDispatcher):
    """Simple JSON-RPC server.

    Simple JSON-RPC server that allows functions and a single instance
    to be installed to handle requests. The default implementation
    attempts to dispatch JSON-RPC calls to the functions or instance
    installed in the server. Override the _dispatch method inhereted
    from SimpleJSONRPCDispatcher to change this behavior.
    """

    allow_reuse_address = True

    # Warning: this is for debugging purposes only! Never set this to True in
    # production code, as will be sending out sensitive information (exception
    # and stack trace details) when exceptions are raised inside
    # SimpleJSONRPCRequestHandler.do_POST
    _send_traceback_header = False

    def __init__(self, addr, requestHandler=SimpleJSONRPCRequestHandler,
            logRequests=True, allow_none=False, encoding=None,
            bind_and_activate=True):
        self.handlers = set()
        self.logRequests = logRequests

        SimpleJSONRPCDispatcher.__init__(self, allow_none, encoding)
        try:
            SocketServer.TCPServer.__init__(self, addr, requestHandler,
                    bind_and_activate)
        except TypeError:
            SocketServer.TCPServer.__init__(self, addr, requestHandler)

        # [Bug #1222790] If possible, set close-on-exec flag; if a
        # method spawns a subprocess, the subprocess shouldn't have
        # the listening socket open.
        if fcntl is not None and hasattr(fcntl, 'FD_CLOEXEC'):
            flags = fcntl.fcntl(self.fileno(), fcntl.F_GETFD)
            flags |= fcntl.FD_CLOEXEC
            fcntl.fcntl(self.fileno(), fcntl.F_SETFD, flags)

    def server_close(self):
        SocketServer.TCPServer.server_close(self)
        for handler in self.handlers.copy():
            self.shutdown_request(handler.request)


class SimpleThreadedJSONRPCServer(SocketServer.ThreadingMixIn,
        SimpleJSONRPCServer):
    timeout = 1
    daemon_threads = True
    disable_nagle_algorithm = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET,
            socket.SO_KEEPALIVE, 1)
        SimpleJSONRPCServer.server_bind(self)


class SimpleThreadedJSONRPCServer6(SimpleThreadedJSONRPCServer):
    address_family = socket.AF_INET6


class SecureThreadedJSONRPCServer(SimpleThreadedJSONRPCServer):

    def __init__(self, server_address, HandlerClass, logRequests=1):
        SimpleThreadedJSONRPCServer.__init__(self, server_address,
            HandlerClass, logRequests)
        self.socket = socket.socket(self.address_family,
            self.socket_type)
        self.server_bind()
        self.server_activate()


class SecureThreadedJSONRPCServer6(SecureThreadedJSONRPCServer):
    address_family = socket.AF_INET6


class JSONRPCDaemon(daemon):

    def __init__(self, interface, port, secure=False):
        daemon.__init__(self, interface, port, secure, name='JSONRPCDaemon')
        if self.secure:
            handler_class = SecureJSONRPCRequestHandler
            server_class = SecureThreadedJSONRPCServer
            if self.ipv6:
                server_class = SecureThreadedJSONRPCServer6
        else:
            handler_class = SimpleJSONRPCRequestHandler
            server_class = SimpleThreadedJSONRPCServer
            if self.ipv6:
                server_class = SimpleThreadedJSONRPCServer6
        self.server = server_class((interface, port), handler_class, 0)
