# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import http.client
import logging
import os
import socket

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from functools import partial

from tryton import bus, device_cookie, fingerprints
from tryton.config import CONFIG, get_config_dir
from tryton.exceptions import TrytonServerError, TrytonServerUnavailable
from tryton.jsonrpc import Fault, ServerPool, ServerProxy

logger = logging.getLogger(__name__)
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
        logger.info('common.db.list()')
        result = connection.common.db.list()
        logger.debug('%r', result)
        return result
    except Fault as exception:
        logger.debug(exception.faultCode)
        if exception.faultCode == str(HTTPStatus.FORBIDDEN.value):
            return []
        else:
            return None


def server_version(host, port):
    try:
        connection = ServerProxy(host, port)
        logger.info('common.server.version(None, None)')
        result = connection.common.server.version()
        logger.debug('%r', result)
        return result
    except Exception as e:
        logger.exception(e)
        return None


def authentication_services(host, port):
    try:
        connection = ServerProxy(host, port)
        logger.info('common.authentication.services()')
        services = connection.common.authentication.services()
        logger.debug('%r', services)
        return connection.url, services
    except Exception as e:
        logger.exception(e)
        return '', []


def set_service_session(parameters):
    from tryton import common
    global CONNECTION, _USER
    host = CONFIG['login.host']
    hostname = common.get_hostname(host)
    port = common.get_port(host)
    database = CONFIG['login.db']
    CONFIG['login.login'] = username = parameters.get('login', [''])[0]
    try:
        user_id = int(parameters.get('user_id', [None])[0])
    except TypeError:
        pass
    session = parameters.get('session', [''])[0]
    if 'renew' in parameters:
        renew_id = int(parameters.get('renew', [-1])[0])
        if _USER != renew_id:
            raise ValueError
    _USER = user_id
    session = ':'.join(map(str, [username, user_id, session]))
    if CONNECTION is not None:
        CONNECTION.close()
    CONNECTION = ServerPool(
        hostname, port, database, session=session, cache=not CONFIG['dev'])
    bus.listen(CONNECTION)


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
    logger.info('common.db.login(%s, %s, %s)', username, 'x' * 10, language)
    result = connection.common.db.login(username, parameters, language)
    logger.debug('%r', result)
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
            logger.info('common.db.logout()')
            with CONNECTION() as conn:
                conn.common.db.logout()
        except (Fault, socket.error, http.client.CannotSendRequest):
            pass
        CONNECTION.close()
        CONNECTION = None
    _USER = None


def reset_password():
    from tryton import common
    host = CONFIG['login.host']
    hostname = common.get_hostname(host)
    port = common.get_port(host)
    database = CONFIG['login.db']
    username = CONFIG['login.login']
    language = CONFIG['client.lang']
    if not all([host, database, username]):
        return
    try:
        connection = ServerProxy(hostname, port, database)
        logger.info('common.db.reset_password(%s, %s)', (username, language))
        connection.common.db.reset_password(username, language)
    except Fault as exception:
        logger.debug(exception.faultCode)


def execute(*args):
    global CONNECTION, _USER
    if CONNECTION is None:
        raise TrytonServerError('403')
    try:
        name = '.'.join(args[:3])
        args = args[3:]
        logger.info('%s%r', name, args)
        with CONNECTION() as conn:
            result = getattr(conn, name)(*args)
    except (http.client.CannotSendRequest, socket.error) as exception:
        raise TrytonServerUnavailable(*exception.args)
    logger.debug('%r', result)
    return result


def clear_cache(prefix=None):
    if CONNECTION:
        CONNECTION.clear_cache(prefix)
