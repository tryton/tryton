#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import errno
import os
import socket
import threading

def endsocket(sock):
    if os.name != 'nt':
        try:
            sock.shutdown(getattr(socket, 'SHUT_RDWR', 2))
        except socket.error, e:
            if e.errno != errno.ENOTCONN: raise
        sock.close()

class daemon(threading.Thread):
    def __init__(self, interface, port, secure, name=None):
        threading.Thread.__init__(self, name=name)
        self.secure = secure
        self.running = False
        self.ipv6 = False
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                self.ipv6 = True
            except Exception:
                pass

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()
        endsocket(self.server.socket)
        return True
