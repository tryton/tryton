#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.config import CONFIG


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

