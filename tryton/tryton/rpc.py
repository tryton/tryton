# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import httplib
import logging
import socket
import ssl
import os
from functools import partial
from tryton.jsonrpc import ServerProxy, ServerPool, Fault
from tryton.fingerprints import Fingerprints
from tryton.config import get_config_dir
from tryton.ipc import Server as IPCServer
from tryton.exceptions import TrytonServerError, TrytonServerUnavailable
from tryton.config import CONFIG

CONNECTION = None
_USER = None
_USERNAME = ''
_HOST = ''
_PORT = None
_DATABASE = ''
CONTEXT = {}
_VIEW_CACHE = {}
_TOOLBAR_CACHE = {}
_KEYWORD_CACHE = {}
_CA_CERTS = os.path.join(get_config_dir(), 'ca_certs')
if not os.path.isfile(_CA_CERTS):
    _CA_CERTS = None
_FINGERPRINTS = Fingerprints()

ServerProxy = partial(ServerProxy, fingerprints=_FINGERPRINTS,
    ca_certs=_CA_CERTS)
ServerPool = partial(ServerPool, fingerprints=_FINGERPRINTS,
    ca_certs=_CA_CERTS)


def db_list(host, port):
    try:
        connection = ServerProxy(host, port)
        logging.getLogger(__name__).info('common.db.list()')
        result = connection.common.db.list()
        logging.getLogger(__name__).debug(repr(result))
        return result
    except Fault, exception:
        if exception.faultCode == 'AccessDenied':
            logging.getLogger(__name__).debug('AccessDenied')
            return []
        else:
            logging.getLogger(__name__).debug(repr(None))
            return None


def server_version(host, port):
    try:
        connection = ServerProxy(host, port)
        logging.getLogger(__name__).info(
            'common.server.version(None, None)')
        result = connection.common.server.version()
        logging.getLogger(__name__).debug(repr(result))
        return result
    except (Fault, socket.error, ssl.SSLError, ssl.CertificateError), e:
        logging.getLogger(__name__).error(e)
        return None


def login(host, port, database, username, parameters, language=None):
    global CONNECTION, _USER, _USERNAME, _HOST, _PORT, _DATABASE
    global _VIEW_CACHE, _TOOLBAR_CACHE, _KEYWORD_CACHE
    connection = ServerProxy(host, port, database)
    logging.getLogger(__name__).info('common.db.login(%s, %s, %s)'
        % (username, 'x' * 10, language))
    result = connection.common.db.login(username, parameters, language)
    logging.getLogger(__name__).debug(repr(result))
    _USER = result[0]
    _USERNAME = username
    session = ':'.join(map(str, [username] + result))
    if CONNECTION is not None:
        CONNECTION.close()
    CONNECTION = ServerPool(host, port, database, session=session)
    _HOST = host
    _PORT = port
    _DATABASE = database
    _VIEW_CACHE = {}
    _TOOLBAR_CACHE = {}
    _KEYWORD_CACHE = {}
    IPCServer(host, port, database).run()


def logout():
    global CONNECTION, _USER, _USERNAME, _HOST, _PORT, _DATABASE
    global _VIEW_CACHE, _TOOLBAR_CACHE, _KEYWORD_CACHE
    if IPCServer.instance:
        IPCServer.instance.stop()
    if CONNECTION is not None:
        try:
            logging.getLogger(__name__).info('common.db.logout()')
            with CONNECTION() as conn:
                conn.common.db.logout()
        except (Fault, socket.error, httplib.CannotSendRequest):
            pass
        CONNECTION.close()
        CONNECTION = None
    _USER = None
    _USERNAME = ''
    _HOST = ''
    _PORT = None
    _DATABASE = ''
    _VIEW_CACHE = {}
    _TOOLBAR_CACHE = {}
    _KEYWORD_CACHE = {}


def _execute(blocking, *args):
    global CONNECTION, _USER
    if CONNECTION is None:
        raise TrytonServerError('403')
    key = False
    model = args[1]
    method = args[2]
    if not CONFIG['dev']:
        if method == 'fields_view_get':
            key = str(args)
            if key in _VIEW_CACHE:
                return _VIEW_CACHE[key]
        elif method == 'view_toolbar_get':
            key = str(args)
            if key in _TOOLBAR_CACHE:
                return _TOOLBAR_CACHE[key]
        elif model == 'ir.action.keyword' and method == 'get_keyword':
            key = str(args)
            if key in _KEYWORD_CACHE:
                return _KEYWORD_CACHE[key]
    try:
        name = '.'.join(args[:3])
        args = args[3:]
        logging.getLogger(__name__).info('%s%s' % (name, args))
        with CONNECTION() as conn:
            result = getattr(conn, name)(*args)
    except (httplib.CannotSendRequest, socket.error), exception:
        raise TrytonServerUnavailable(*exception.args)
    if not CONFIG['dev']:
        if key and method == 'fields_view_get':
            _VIEW_CACHE[key] = result
        elif key and method == 'view_toolbar_get':
            _TOOLBAR_CACHE[key] = result
        elif key and model == 'ir.action.keyword' and method == 'get_keyword':
            _KEYWORD_CACHE[key] = result
    logging.getLogger(__name__).debug(repr(result))
    return result


def execute(*args):
    return _execute(True, *args)


def execute_nonblocking(*args):
    return _execute(False, *args)
