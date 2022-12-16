#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import socket
# can't use/fall-back pickle due to different interface :-(
import cPickle
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
try:
    import ssl
except ImportError:
    ssl = None
import gzip

DNS_CACHE = {}
MAX_SIZE = 999999999
MAX_LENGHT = len(str(MAX_SIZE))
CONNECT_TIMEOUT = 5
TIMEOUT = 3600
GZIP_THRESHOLD = 1400 # common MTU

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
        self.hostname = None
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
                self.sock.settimeout(CONNECT_TIMEOUT)
                self.sock.connect((host, int(port)))
            except Exception:
                self.sock = None
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(CONNECT_TIMEOUT)
            self.sock.connect((host, int(port)))
        DNS_CACHE[hostname], port = self.sock.getpeername()[:2]
        try:
            sock = None
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(host, int(port), socket.AF_INET6)
                    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    sock.settimeout(CONNECT_TIMEOUT)
                    sock.connect((host, int(port)))
                except Exception:
                    sock = None
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECT_TIMEOUT)
                sock.connect((host, int(port)))
            if ssl:
                ssl.wrap_socket(sock)
                self.ssl = True
            elif hasattr(socket, 'ssl'):
                socket.ssl(sock)
                self.ssl = True
        except Exception:
            pass
        self.sock.settimeout(TIMEOUT)
        if self.ssl:
            if ssl:
                self.ssl_sock = ssl.wrap_socket(self.sock)
            elif hasattr(socket, 'ssl'):
                self.ssl_sock = socket.ssl(self.sock)
        self.host = host
        self.hostname = hostname
        self.port = port
        self.connected = True
        self.buffer = ''

    def disconnect(self):
        try:
            sock = self.sock
            if self.ssl:
                sock = self.ssl_sock
            try:
                shutdown_value = 2
                if hasattr(socket, 'SHUT_RDWR'):
                    shutdown_value = socket.SHUT_RDWR
                if hasattr(sock, 'sock_shutdown'):
                    sock.sock_shutdown(shutdown_value)
                else:
                    sock.shutdown(shutdown_value)
            except Exception:
                pass
            sock.close()
        except Exception:
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
        gzip_p = False
        if len(msg) > GZIP_THRESHOLD:
            buf = StringIO.StringIO()
            output = gzip.GzipFile(mode='wb', fileobj=buf)
            output.write(msg)
            output.close()
            buf.seek(0)
            msg = buf.getvalue()
            gzip_p = True
        size = len(msg)
        msg = str(size) + ' ' + (exception and "1" or "0") \
                + (gzip_p and "1" or "0") + msg
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
        buf_list = []
        size_remaining = MAX_LENGHT
        while size_remaining:
            chunk_size = min(size_remaining, 4096)
            if self.ssl:
                chunk = self.ssl_sock.read(chunk_size)
            else:
                chunk = self.sock.recv(chunk_size)
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            buf_list.append(chunk)
            size_remaining -= len(chunk)
            if ' ' in chunk:
                break
        if size_remaining < 0:
            raise RuntimeError, "socket connection broken"
        buf += ''.join(buf_list)
        size, msg = buf.split(' ', 1)
        size = int(size)
        if size > MAX_SIZE:
            raise RuntimeError, "socket connection broken"
        while len(msg) < 2:
            chunk_size = min(size + 2, 4096)
            if self.ssl:
                msg += self.ssl_sock.read(chunk_size)
            else:
                msg += self.sock.recv(chunk_size)
            if msg == '':
                raise RuntimeError, "socket connection broken"
        exception = msg[0] != "0"
        gzip_p = msg[1] != "0"
        buf_list = [msg[2:]]
        size_remaining = size - len(buf_list[0])
        while size_remaining:
            chunk_size = min(size_remaining, 4096)
            if self.ssl:
                chunk = self.ssl_sock.read(chunk_size)
            else:
                chunk = self.sock.recv(chunk_size)
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            buf_list.append(chunk)
            size_remaining -= len(chunk)
        msg = ''.join(buf_list)
        if len(msg) > size:
            self.buffer = msg[size:]
            msg = msg[:size]
        else:
            self.buffer = ''
        msgio = StringIO.StringIO(msg)
        if gzip_p:
            output = gzip.GzipFile(mode='r', fileobj=msgio)
            msgio = StringIO.StringIO(output.read(-1))
            output.close()
        unpickler = cPickle.Unpickler(msgio)
        # cPickle mechanism to import instances (pickle differs here)
        unpickler.find_global = checkfunction
        res = unpickler.load()
        if exception:
            raise Exception(*(list(res[0]) + [res[1]]))
        else:
            return res[0]
