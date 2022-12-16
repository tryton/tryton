#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.config import CONFIG


def SSLSocket(socket):
    # Let the import error raise only when used
    import ssl
    return ssl.wrap_socket(socket,
        server_side=True,
        certfile=CONFIG['certificate'],
        keyfile=CONFIG['privatekey'],
        ssl_version=ssl.PROTOCOL_SSLv23)
