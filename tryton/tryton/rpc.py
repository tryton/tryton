#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import pysocket
import logging
import socket
from threading import Semaphore

_SOCK = None
_USER = 0
_USERNAME = ''
_SESSION = ''
_DATABASE = ''
CONTEXT = {}
_VIEW_CACHE = {}
TIMEZONE = 'utc'
SECURE = False
_SEMAPHORE = Semaphore()

def db_list(host, port):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK = pysocket.PySocket()
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            try:
                _SOCK.send(('db', 'list'))
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(('db', 'list'))
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        return res
    except:
        return None

def db_exec(host, port, method, *args):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK= pysocket.PySocket()
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            try:
                _SOCK.send(('db', method) + args)
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(('db', method) + args)
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        return res
    except:
        raise

def server_version(host, port):
    global _SOCK, SECURE
    _SEMAPHORE.acquire()
    try:
        try:
            if _SOCK and (_SOCK.hostname != host or _SOCK.port != port):
                _SOCK.disconnect()
            if _SOCK is None:
                _SOCK = pysocket.PySocket()
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            try:
                _SOCK.send(('common', 'version'))
            except Exception, exception:
                if exception[0] == 32:
                    _SOCK.reconnect()
                    _SOCK.send(('db', 'list'))
                else:
                    raise
            res = _SOCK.receive()
            SECURE = _SOCK.ssl
        finally:
            _SEMAPHORE.release()
        return res
    except:
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
                _SOCK = pysocket.PySocket()
            if not _SOCK.connected:
                _SOCK.connect(host, port)
            _SOCK.send(('common', 'login', database, username, password))
            res = _SOCK.receive()
        finally:
            _SEMAPHORE.release()
    except (socket.error, RuntimeError):
        try:
            _SOCK.reconnect()
        except (socket.error, RuntimeError):
            pass
        _USER = 0
        _SESSION = ''
        return -1
    if not res:
        _USER = 0
        _SESSION = ''
        return -2
    _USER = res[0]
    _USERNAME = username
    _SESSION = res[1]
    _DATABASE = database
    SECURE = _SOCK.ssl
    context_reload()
    return 1

def logout():
    global _SOCK, _USER, _USERNAME, _SESSION, _DATABASE, _VIEW_CACHE, SECURE
    if _SOCK:
        _SOCK.disconnect()
        _SOCK = None
    _USER = 0
    _USERNAME = ''
    _SESSION = ''
    _DATABASE = ''
    _VIEW_CACHE = {}
    SECURE = False

def context_reload():
    global CONTEXT, TIMEZONE
    user = RPCProxy('res.user')
    try:
        context = user.get_preferences(True, {})
    except:
        return
    CONTEXT = {}
    for i in context:
        value = context[i]
        CONTEXT[i] = value
        if i == 'timezone':
            try:
                TIMEZONE = execute('common', 'timezone_get')
            except:
                pass

def _execute(blocking, obj, method, *args):
    global _SOCK, _DATABASE, _USER, _SESSION
    if not _SOCK or not _SOCK.connected:
        raise Exception('NotLogged')
    logging.getLogger('rpc.request').info(str((obj, method, args)))
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
            _SOCK.send((obj, method, _DATABASE, _USER, _SESSION) + args)
            result = _SOCK.receive()
        except (socket.error, RuntimeError):
            try:
                _SOCK.reconnect()
                _SOCK.send((obj, method, _DATABASE, _USER, _SESSION) + args)
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
    return result

def execute(obj, method, *args):
    return _execute(True, obj, method, *args)

def execute_nonblocking(obj, method, *args):
    return _execute(False, obj, method, *args)

class RPCProxy(object):

    def __init__(self, name):
        self.name = name
        self.__attrs = {}

    def __getattr__(self, attr):
        if attr not in self.__attrs:
            self.__attrs[attr] = RPCFunction(self.name, attr)
        return self.__attrs[attr]

class RPCFunction(object):

    def __init__(self, name, func_name):
        self.name = name
        self.func = func_name

    def __call__(self, *args):
        return execute('object', 'execute', self.name, self.func, *args)
