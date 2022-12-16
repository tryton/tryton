#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import pysocket
import logging
import socket
import os
from threading import Semaphore
from tryton.fingerprints import Fingerprints
from tryton.config import get_config_dir
from tryton.ipc import Server as IPCServer

_SOCK = None
_USER = None
_USERNAME = ''
_SESSION = ''
_DATABASE = ''
CONTEXT = {}
_VIEW_CACHE = {}
TIMEZONE = 'utc'
SECURE = False
_SEMAPHORE = Semaphore()
_CA_CERTS = os.path.join(get_config_dir(), 'ca_certs')

def db_list(host, port):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK = pysocket.PySocket(fingerprints=Fingerprints(),
                        ca_certs=_CA_CERTS)
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            args = (None, None, None, 'common', 'db', 'list')
            logging.getLogger('rpc.request').info(repr(args))
            try:
                _SOCK.send(args)
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(args)
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        logging.getLogger('rpc.result').debug(repr(res))
        return res
    except Exception, exception:
        if exception[0] == 'AccessDenied':
            raise
        else:
            logging.getLogger('rpc.result').debug(repr(None))
            return None

def db_exec(host, port, method, *args):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK= pysocket.PySocket(fingerprints=Fingerprints(),
                        ca_certs=_CA_CERTS)
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            args = (None, None, None, 'common', 'db', method) + args
            logging.getLogger('rpc.request').info(repr(args))
            try:
                _SOCK.send(args)
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(args)
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        logging.getLogger('rpc.result').debug(repr(res))
        return res
    except Exception:
        raise

def server_version(host, port):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK = pysocket.PySocket(fingerprints=Fingerprints(),
                        ca_certs=_CA_CERTS)
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            args = (None, None, None, 'common', None, 'version')
            logging.getLogger('rpc.request').info(repr(args))
            try:
                _SOCK.send(args)
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(args)
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        logging.getLogger('rpc.result').debug(repr(res))
        return res
    except Exception:
        logging.getLogger('rpc.result').debug(repr(None))
        return None

def login(username, password, host, port, database):
    global _SOCK, _USER, _USERNAME, _SESSION, _DATABASE, _VIEW_CACHE, SECURE
    _VIEW_CACHE = {}
    SECURE = False
    try:
        _SEMAPHORE.acquire()
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK = pysocket.PySocket(fingerprints=Fingerprints(),
                        ca_certs=_CA_CERTS)
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            args = (database, username, password, 'common', 'db', 'login')
            logging.getLogger('rpc.request').info(repr(args))
            _SOCK.send(args)
            res = _SOCK.receive()
            logging.getLogger('rpc.result').debug(repr(res))
        finally:
            _SEMAPHORE.release()
    except (socket.error, RuntimeError):
        try:
            _SOCK.reconnect()
        except (socket.error, RuntimeError):
            pass
        _USER = None
        _SESSION = ''
        return -1
    if not res:
        _USER = None
        _SESSION = ''
        return -2
    _USER = res[0]
    _USERNAME = username
    _SESSION = res[1]
    _DATABASE = database
    SECURE = _SOCK.ssl
    context_reload()
    IPCServer(host, port, database).run()
    return 1

def logout():
    global _SOCK, _USER, _USERNAME, _SESSION, _DATABASE, _VIEW_CACHE, SECURE
    if IPCServer.instance:
        IPCServer.instance.stop()
    if _SOCK and _USER:
        try:
            _SEMAPHORE.acquire()
            try:
                args = (_DATABASE, _USER, _SESSION, 'common', 'db', 'logout')
                logging.getLogger('rpc.request').info(repr(args))
                _SOCK.sock.settimeout(pysocket.CONNECT_TIMEOUT)
                _SOCK.send(args)
                res = _SOCK.receive()
                logging.getLogger('rpc.result').debug(repr(res))
            finally:
                _SEMAPHORE.release()
        except Exception:
            pass
        _SOCK.disconnect()
        _SOCK = None
    _USER = None
    _USERNAME = ''
    _SESSION = ''
    _DATABASE = ''
    _VIEW_CACHE = {}
    SECURE = False

def context_reload():
    global CONTEXT, TIMEZONE
    try:
        context = execute('model', 'res.user', 'get_preferences', True, {})
    except Exception:
        return
    CONTEXT = {}
    for i in context:
        value = context[i]
        CONTEXT[i] = value
        if i == 'timezone':
            try:
                TIMEZONE = execute('common', None, 'timezone_get')
            except Exception:
                pass

def _execute(blocking, *args):
    global _SOCK, _DATABASE, _USER, _SESSION
    if not _SOCK or not _SOCK.connected:
        raise Exception('NotLogged')
    logging.getLogger('rpc.request').info(repr((args)))
    key = False
    if len(args) >= 6 and args[1] == 'fields_view_get':
        key = str(args)
        if key in _VIEW_CACHE and _VIEW_CACHE[key][0]:
            args = args[:]
            args = args + (_VIEW_CACHE[key][0],)
    res = _SEMAPHORE.acquire(blocking)
    if not res:
        return
    try:
        try:
            _SOCK.send((_DATABASE, _USER, _SESSION) + args)
            result = _SOCK.receive()
        except (socket.error, RuntimeError):
            try:
                _SOCK.reconnect()
                _SOCK.send((_DATABASE, _USER, _SESSION) + args)
                result = _SOCK.receive()
            except (socket.error, RuntimeError):
                _SOCK.reconnect()
                raise
    finally:
        _SEMAPHORE.release()
    if key:
        if result is True and key in _VIEW_CACHE:
            result = _VIEW_CACHE[key][1]
        else:
            _VIEW_CACHE[key] = (result['md5'], result)
    logging.getLogger('rpc.result').debug(repr(result))
    return result

def execute(*args):
    return _execute(True, *args)

def execute_nonblocking(*args):
    return _execute(False, *args)
