#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import socket
# can't use/fall-back pickle due to different interface :-(
import cPickle
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

DNS_CACHE = {}
MAX_SIZE = 999999999
MAX_LENGHT = len(str(MAX_SIZE))
TIMEOUT = 120

_ALLOWED_MODULES = {'datetime': ['datetime', 'date'], 'decimal': ['Decimal']}

def checkfunction(module, klass):
    if module in _ALLOWED_MODULES and klass in _ALLOWED_MODULES[module]:
        mod = __import__(module, {}, {}, ['__all__'])
        _class = getattr(mod, klass)
        return _class
    raise ValueError('Not supported: %s/%s' % (module, klass))


class PySocket:

    def __init__(self, sock=None):
        self.sock = sock
        self.host = None
        self.port = None
        self.ssl = False
        self.ssl_sock = None
        self.connected = False
        self.buffer = ''

    def connect(self, host, port=False):
        if not port:
            buf = host.split('//')[1]
            host, port = buf.rsplit(':', 1)
        hostname = host
        if host in DNS_CACHE:
            host = DNS_CACHE[host]
        self.sock = None
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(host, int(port), socket.AF_INET6)
                self.sock = socket.socket(socket.AF_INET6,
                        socket.SOCK_STREAM)
                self.sock.settimeout(TIMEOUT)
                self.sock.connect((host, int(port)))
            except:
                self.sock = None
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(TIMEOUT)
            self.sock.connect((host, int(port)))
        DNS_CACHE[hostname], port = self.sock.getpeername()[:2]
        try:
            sock = None
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(host, int(port), socket.AF_INET6)
                    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    sock.settimeout(TIMEOUT)
                    sock.connect((host, int(port)))
                except:
                    sock = None
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(TIMEOUT)
                sock.connect((host, int(port)))
            if hasattr(socket, 'ssl'):
                ssl_sock = socket.ssl(sock)
                self.ssl = True
        except:
            pass
        if self.ssl:
            self.ssl_sock = socket.ssl(self.sock)
        self.host = host
        self.hostname = hostname
        self.port = port
        self.connected = True
        self.buffer = ''

    def disconnect(self):
        try:
            if self.ssl:
                try:
                    if hasattr(socket, 'SHUT_RDWR'):
                        self.ssl_sock.sock_shutdown(socket.SHUT_RDWR)
                    else:
                        self.ssl_sock.sock_shutdown(2)
                except:
                    pass
                self.ssl_sock.close()
            else:
                try:
                    if hasattr(socket, 'SHUT_RDWR'):
                        self.sock.shutdown(socket.SHUT_RDWR)
                    else:
                        self.sock.shutdown(2)
                except:
                    pass
                self.sock.close()
        except:
            pass
        self.sock = None
        self.ssl = False
        self.ssl_sock = None
        self.connected = False
        self.buffer = ''

    def reconnect(self):
        if self.host and self.port:
            self.disconnect()
            self.connect(self.host, self.port)

    def send(self, msg, exception=False, traceback=None):
        msg = cPickle.dumps([msg, traceback], protocol=2)
        size = len(msg)
        msg = str(size) + ' ' + (exception and "1" or "0") + msg
        size = len(msg)
        totalsent = 0
        while totalsent < size:
            if self.ssl:
                sent = self.ssl_sock.write(msg[totalsent:])
            else:
                sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError, "socket connection broken"
            totalsent = totalsent + sent

    def receive(self):
        buf = self.buffer
        while len(buf) < MAX_LENGHT:
            if self.ssl:
                chunk = self.ssl_sock.read(4096)
            else:
                chunk = self.sock.recv(4096)
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            buf += chunk
            if ' ' in buf:
                break
        size, msg = buf.split(' ', 1)
        size = int(size)
        if msg == '':
            if self.ssl:
                msg = self.ssl_sock.read(4096)
            else:
                msg = self.sock.recv(4096)
            if msg == '':
                raise RuntimeError, "socket connection broken"
        if msg[0] != "0":
            exception = buf
        else:
            exception = False
        msg = msg[1:]
        while len(msg) < size:
            if self.ssl:
                chunk = self.ssl_sock.read(size - len(msg))
            else:
                chunk = self.sock.recv(size - len(msg))
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            msg = msg + chunk
        self.buffer = msg[size:]
        msg = msg[:size]
        msgio = StringIO.StringIO(msg)
        unpickler = cPickle.Unpickler(msgio)
        # cPickle mechanism to import instances (pickle differs here)
        unpickler.find_global = checkfunction
        res = unpickler.load()
        if exception:
            raise Exception(*(list(res[0]) + [res[1]]))
        else:
            return res[0]
