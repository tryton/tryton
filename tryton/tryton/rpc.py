# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import http.client
import logging
import socket
import os
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from functools import partial

from tryton import bus, device_cookie, fingerprints
from tryton.jsonrpc import ServerProxy, ServerPool, Fault
from tryton.config import get_config_dir
from tryton.exceptions import TrytonServerError, TrytonServerUnavailable
from tryton.config import CONFIG

CONNECTION = None
_USER = None
CONTEXT = {}
_VIEW_CACHE = {}
_TOOLBAR_CACHE = {}
_KEYWORD_CACHE = {}
_CA_CERTS = os.path.join(get_config_dir(), 'ca_certs')
if not os.path.isfile(_CA_CERTS):
    _CA_CERTS = None

ServerProxy = partial(ServerProxy, fingerprints=fingerprints,
    ca_certs=_CA_CERTS)
ServerPool = partial(ServerPool, fingerprints=fingerprints,
    ca_certs=_CA_CERTS)


def context_reset():
    CONTEXT.clear()
    CONTEXT['client'] = bus.ID


context_reset()


def db_list(host, port):
    try:
        connection = ServerProxy(host, port)
        logging.getLogger(__name__).info('common.db.list()')
        result = connection.common.db.list()
        logging.getLogger(__name__).debug(repr(result))
        return result
    except Fault as exception:
        logging.getLogger(__name__).debug(exception.faultCode)
        if exception.faultCode == str(HTTPStatus.FORBIDDEN.value):
            return []
        else:
            return None


def server_version(host, port):
    try:
        connection = ServerProxy(host, port)
        logging.getLogger(__name__).info(
            'common.server.version(None, None)')
        result = connection.common.server.version()
        logging.getLogger(__name__).debug(repr(result))
        return result
    except Exception as e:
        logging.getLogger(__name__).error(e)
        return None


def login(parameters):
    from tryton import common
    global CONNECTION, _USER
    host = CONFIG['login.host']
    hostname = common.get_hostname(host)
    port = common.get_port(host)
    database = CONFIG['login.db']
    username = CONFIG['login.login']
    language = CONFIG['client.lang']
    parameters['device_cookie'] = device_cookie.get()
    connection = ServerProxy(hostname, port, database)
    logging.getLogger(__name__).info('common.db.login(%s, %s, %s)'
        % (username, 'x' * 10, language))
    result = connection.common.db.login(username, parameters, language)
    logging.getLogger(__name__).debug(repr(result))
    _USER = result[0]
    session = ':'.join(map(str, [username] + result))
    if CONNECTION is not None:
        CONNECTION.close()
    CONNECTION = ServerPool(
        hostname, port, database, session=session, cache=not CONFIG['dev'])
    device_cookie.renew()
    bus.listen(CONNECTION)


def logout():
    global CONNECTION, _USER
    if CONNECTION is not None:
        try:
            logging.getLogger(__name__).info('common.db.logout()')
            with CONNECTION() as conn:
                conn.common.db.logout()
        except (Fault, socket.error, http.client.CannotSendRequest):
            pass
        CONNECTION.close()
        CONNECTION = None
    _USER = None


def execute(*args):
    global CONNECTION, _USER
    if CONNECTION is None:
        raise TrytonServerError('403')
    try:
        name = '.'.join(args[:3])
        args = args[3:]
        logging.getLogger(__name__).info('%s%s' % (name, args))
        with CONNECTION() as conn:
            result = getattr(conn, name)(*args)
    except (http.client.CannotSendRequest, socket.error) as exception:
        raise TrytonServerUnavailable(*exception.args)
    logging.getLogger(__name__).debug(repr(result))
    return result


def clear_cache(prefix=None):
    if CONNECTION:
        CONNECTION.clear_cache(prefix)
