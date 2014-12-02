# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import errno
import os
import socket
import threading
from SocketServer import StreamRequestHandler


def endsocket(sock):
    if os.name != 'nt':
        try:
            sock.shutdown(getattr(socket, 'SHUT_RDWR', 2))
        except socket.error, e:
            if e.errno != errno.ENOTCONN:
                raise
        sock.close()


class daemon(threading.Thread):
    def __init__(self, interface, port, secure, name=None):
        threading.Thread.__init__(self, name=name)
        self.secure = secure
        self.ipv6 = False
        for family, _, _, _, _ in socket.getaddrinfo(interface or None, port,
                socket.AF_UNSPEC, socket.SOCK_STREAM):
            if family == socket.AF_INET6:
                self.ipv6 = True
            break

    def stop(self):
        self.server.shutdown()
        self.server.socket.shutdown(socket.SHUT_RDWR)
        self.server.server_close()
        return

    def run(self):
        self.server.serve_forever()
        return True


class RegisterHandlerMixin:

    def setup(self):
        self.server.handlers.add(self)
        StreamRequestHandler.setup(self)

    def finish(self):
        StreamRequestHandler.finish(self)
        try:
            self.server.handlers.remove(self)
        except KeyError:
            pass
