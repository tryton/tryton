#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
"""
Miscelleanous tools used by tryton
"""
import os, time, sys
import inspect
from trytond.config import CONFIG
import socket
import subprocess
import zipfile
from trytond.backend import Database
from threading import Lock, local
import logging
import smtplib
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import dis
import datetime

def find_in_path(name):
    if os.name == "nt":
        sep = ';'
    else:
        sep = ':'
    path = [directory for directory in os.environ['PATH'].split(sep)
            if os.path.isdir(directory)]
    for directory in path:
        val = os.path.join(directory, name)
        if os.path.isfile(val) or os.path.islink(val):
            return val
    return name

def find_pg_tool(name):
    if CONFIG['pg_path'] and CONFIG['pg_path'] != 'None':
        return os.path.join(CONFIG['pg_path'], name)
    else:
        return find_in_path(name)

def exec_pg_command(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    args2 = (os.path.basename(prog),) + args
    return os.spawnv(os.P_WAIT, prog, args2)

def exec_pg_command_pipe(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"' + prog + '" ' + ' '.join(args)
    else:
        cmd = prog + ' ' + ' '.join(args)

    # if db_password is set in configuration we should pass
    # an environment variable PGPASSWORD to our subprocess
    # see libpg documentation
    child_env = dict(os.environ)
    if CONFIG['db_password']:
        child_env['PGPASSWORD'] = CONFIG['db_password']
    pipe = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, env=child_env)
    return pipe

def exec_command_pipe(name, *args):
    prog = find_in_path(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"'+prog+'" '+' '.join(args)
    else:
        cmd = prog+' '+' '.join(args)
    return os.popen2(cmd, 'b')

def file_open(name, mode="r", subdir='modules'):
    """Open a file from the root dir, using a subdir folder."""
    from trytond.modules import EGG_MODULES
    root_path = os.path.dirname(os.path.dirname(__file__))

    name3 = False
    if subdir == 'modules':
        module_name = name.split(os.sep)[0]
        if module_name in EGG_MODULES:
            ep = EGG_MODULES[module_name]
            mod_path = os.path.join(ep.dist.location,
                    *ep.module_name.split('.')[:-1])
            name3 = os.path.join(mod_path, name)

    if subdir:
        if subdir == 'modules'\
                and (name.startswith('ir' + os.sep) \
                    or name.startswith('workflow' + os.sep) \
                    or name.startswith('res' + os.sep) \
                    or name.startswith('webdav' + os.sep) \
                    or name.startswith('tests' + os.sep)):
            name = os.path.join(root_path, name)
        else:
            name = os.path.join(root_path, subdir, name)
    else:
        name = os.path.join(root_path, name)

    # Check for a zipfile in the path
    head = name
    zipname = False
    name2 = False
    while True:
        head, tail = os.path.split(head)
        if head == root_path:
            break
        if not tail:
            break
        if zipname:
            zipname = os.path.join(tail, zipname)
        else:
            zipname = tail
        if zipfile.is_zipfile(head+'.zip'):
            zfile = zipfile.ZipFile(head+'.zip')
            try:
                return StringIO.StringIO(zfile.read(os.path.join(
                    os.path.basename(head), zipname).replace(
                        os.sep, '/')))
            except:
                name2 = os.path.normpath(os.path.join(head + '.zip', zipname))
    for i in (name2, name, name3):
        if i and os.path.isfile(i):
            return file(i, mode)

    raise IOError, 'File not found : '+str(name)

def get_smtp_server():
    """
    Instanciate, configure and return a SMTP or SMTP_SSL instance from
    smtplib.
    :return: A SMTP instance. The quit() method must be call when all
    the calls to sendmail() have been made.
    """
    if CONFIG['smtp_ssl']:
        smtp_server = smtplib.SMTP_SSL(CONFIG['smtp_server'],
                CONFIG['smtp_port'])
    else:
        smtp_server = smtplib.SMTP(CONFIG['smtp_server'], CONFIG['smtp_port'])

    if CONFIG['smtp_tls']:
        smtp_server.starttls()

    if CONFIG['smtp_user'] and CONFIG['smtp_password']:
        smtp_server.login(CONFIG['smtp_user'], CONFIG['smtp_password'])

    return smtp_server

def sms_send(user, password, api_id, text, to):
    "text must be latin-1 encoded"
    import urllib
    params = urllib.urlencode({
        'user': user,
        'password': password,
        'api_id': api_id,
        'text': text,
        'to':to,
        })
    #urllib.urlopen("http://api.clickatell.com/http/sendmsg", params)
    urllib.urlopen("http://196.7.150.220/http/sendmsg", params)
    return True

def find_language_context(args, kargs=None):
    if kargs is None:
        kargs = {}
    res = 'en_US'
    for arg in args:
        if isinstance(arg, dict):
            res = arg.get('language', 'en_US')
    return kargs.get('context', {}).get('language', res)


class Cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """
    _cache_instance = []
    _resets = {}
    _resets_lock = Lock()

    def __init__(self, name, timeout=3600, max_len=1024):
        self.timeout = timeout
        self.max_len = max_len
        self._cache = {}
        self._cache_instance.append(self)
        self._name = name
        self._timestamp = None
        self._lock = Lock()

    def __call__(self, function):
        arg_names = inspect.getargspec(function)[0][2:]

        def cached_result(self2, cursor=None, *args, **kwargs):
            result = None
            find = False
            if isinstance(cursor, basestring):
                Cache.reset(cursor, self._name)
                self._lock.acquire()
                try:
                    self._cache[cursor] = {}
                finally:
                    self._lock.release()
                return True
            # Update named arguments with positional argument values
            kwargs_origin = kwargs.copy()
            kwargs.update(dict(zip(arg_names, args)))
            if 'context' in kwargs:
                if isinstance(kwargs['context'], dict):
                    kwargs['context'] = kwargs['context'].copy()
                    for i in ('_timestamp', '_delete', '_create_records',
                            '_delete_records'):
                        if i in kwargs['context']:
                            del kwargs['context'][i]
            kwargs = kwargs.items()
            kwargs.sort()

            self._lock.acquire()
            try:
                self._cache.setdefault(cursor.dbname, {})
            finally:
                self._lock.release()

            lower = None
            self._lock.acquire()
            try:
                if len(self._cache[cursor.dbname]) > self.max_len:
                    mintime = time.time() - self.timeout
                    for key in self._cache[cursor.dbname].keys():
                        last_time = self._cache[cursor.dbname][key][1]
                        if mintime > last_time:
                            del self._cache[cursor.dbname][key]
                        else:
                            if not lower or lower[1] > last_time:
                                lower = (key, last_time)
                if len(self._cache[cursor.dbname]) > self.max_len and lower:
                    del self._cache[cursor.dbname][lower[0]]
            finally:
                self._lock.release()

            # Work out key as a tuple
            key = (id(self2), repr(kwargs))

            # Check cache and return cached value if possible
            self._lock.acquire()
            try:
                if key in self._cache[cursor.dbname]:
                    (value, last_time) = self._cache[cursor.dbname][key]
                    mintime = time.time() - self.timeout
                    if self.timeout <= 0 or mintime <= last_time:
                        self._cache[cursor.dbname][key] = (value, time.time())
                        result = value
                        find = True
            finally:
                self._lock.release()

            if not find:
                # Work out new value, cache it and return it
                # Should copy() this value to avoid futur modf of the cacle ?
                result = function(self2, cursor, *args, **kwargs_origin)

                self._lock.acquire()
                try:
                    self._cache[cursor.dbname][key] = (result, time.time())
                finally:
                    self._lock.release()
            return result

        cached_result.__doc__ = function.__doc__
        return cached_result

    @staticmethod
    def clean(dbname):
        if not CONFIG['multi_server']:
            return
        database = Database(dbname).connect()
        cursor = database.cursor()
        try:
            cursor.execute('SELECT "timestamp", "name" FROM ir_cache')
            timestamps = {}
            for timestamp, name in cursor.fetchall():
                timestamps[name] = timestamp
        finally:
            cursor.commit()
            cursor.close()
        for obj in Cache._cache_instance:
            if obj._name in timestamps:
                if not obj._timestamp or timestamps[obj._name] > obj._timestamp:
                    obj._timestamp = timestamps[obj._name]
                    obj._lock.acquire()
                    try:
                        obj._cache[dbname] = {}
                    finally:
                        obj._lock.release()

    @staticmethod
    def reset(dbname, name):
        if not CONFIG['multi_server']:
            return
        Cache._resets_lock.acquire()
        try:
            Cache._resets.setdefault(dbname, set())
            Cache._resets[dbname].add(name)
        finally:
            Cache._resets_lock.release()
        return

    @staticmethod
    def resets(dbname):
        if not CONFIG['multi_server']:
            return
        database = Database(dbname).connect()
        cursor = database.cursor()
        Cache._resets_lock.acquire()
        Cache._resets.setdefault(dbname, set())
        try:
            for name in Cache._resets[dbname]:
                cursor.execute('SELECT name FROM ir_cache WHERE name = %s',
                            (name,))
                if cursor.fetchone():
                    cursor.execute('UPDATE ir_cache SET "timestamp" = %s '\
                            'WHERE name = %s', (datetime.datetime.now(), name))
                else:
                    cursor.execute('INSERT INTO ir_cache ("timestamp", "name") ' \
                            'VALUES (%s, %s)', (datetime.datetime.now(), name))
            Cache._resets[dbname].clear()
        finally:
            cursor.commit()
            cursor.close()
            Cache._resets_lock.release()


def mod10r(number):
    """
    Recursive mod10

    :param number: a number
    :return: the same number completed with the recursive modulo base 10
    """
    codec = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    report = 0
    result = ""
    for digit in number:
        result += digit
        if digit.isdigit():
            report = codec[ (int(digit) + report) % 10 ]
    return result + str((10 - report) % 10)


class LocalDict(local):

    def __init__(self, dict=None):
        if dict is None:
            dict = {}
        self.dict = dict

    def __str__(self):
        return str(self.dict)

    def __repr__(self):
        return str(self.dict)

    def clear(self):
        return self.dict.clear()

    def keys(self):
        return self.dict.keys()

    def __setitem__(self, i, y):
        self.dict.__setitem__(i, y)

    def __getitem__(self, i):
        return self.dict.__getitem__(i)

    def copy(self):
        return self.dict.copy()

    def iteritems(self):
        return self.dict.iteritems()

    def iterkeys(self):
        return self.dict.iterkeys()

    def itervalues(self):
        return self.dict.itervalues()

    def pop(self, k, d=None):
        return self.dict.pop(k, d)

    def popitem(self):
        return self.dict.popitem()

    def setdefault(self, k, d=None):
        return self.dict.setdefault(k, d)

    def update(self, E, **F):
        return self.dict.update(E, F)

    def values(self):
        return self.dict.values()

    def get(self, k, d=None):
        return self.dict.get(k, d)

    def has_key(self, k):
        return self.dict.has_key(k)

    def items(self):
        return self.dict.items()

    def __cmp__(self, y):
        return self.dict.__cmp__(y)

    def __contains__(self, k):
        return self.dict.__contains__(k)

    def __delitem__(self, y):
        return self.dict.__delitem__(y)

    def __eq__(self, y):
        return self.dict.__eq__(y)

    def __ge__(self, y):
        return self.dict.__ge__(y)

    def __getitem__(self, y):
        return self.dict.__getitem__(y)

    def __gt__(self, y):
        return self.dict.__gt__(y)

    def __hash__(self):
        return self.dict.__hash__()

    def __iter__(self):
        return self.dict.__iter__()

    def __le__(self, y):
        return self.dict.__le__(y)

    def __len__(self):
        return self.dict.__len__()

    def __lt__(self, y):
        return self.dict.__lt__(y)

    def __ne__(self, y):
        return self.dict.__ne__(y)

def reduce_ids(field, ids):
    '''
    Return a small SQL clause for ids

    :param field: the field of the clause
    :param ids: the list of ids
    :return: sql string and sql param
    '''
    if not ids:
        return '(%s)', [False]
    ids = ids[:]
    ids.sort()
    prev = ids.pop(0)
    continue_list = [prev, prev]
    discontinue_list = []
    sql = []
    args = []
    for i in ids:
        if i == prev:
            continue
        if i != prev + 1:
            if continue_list[-1] - continue_list[0] < 5:
                discontinue_list.extend([continue_list[0] + x for x in
                    range(continue_list[-1] - continue_list[0] + 1)])
            else:
                sql.append('((' + field + ' >= %s) AND (' + field + ' <= %s))')
                args.append(continue_list[0])
                args.append(continue_list[-1])
            continue_list = []
        continue_list.append(i)
        prev = i
    if continue_list[-1] - continue_list[0] < 5:
        discontinue_list.extend([continue_list[0] + x for x in
            range(int(continue_list[-1] - continue_list[0] + 1))])
    else:
        sql.append('((' + field + ' >= %s) AND (' + field + ' <= %s))')
        args.append(continue_list[0])
        args.append(continue_list[-1])
    if discontinue_list:
        sql.append('(' + field + ' IN (' + \
                ','.join(('%s',) * len(discontinue_list)) + '))')
        args.extend(discontinue_list)
    return '(' + ' OR '.join(sql) + ')', args

_ALLOWED_CODES = set(dis.opmap[x] for x in [
    'POP_TOP','ROT_TWO','ROT_THREE','ROT_FOUR','DUP_TOP',
    'BUILD_LIST','BUILD_MAP','BUILD_TUPLE',
    'LOAD_CONST','RETURN_VALUE','STORE_SUBSCR',
    'UNARY_POSITIVE','UNARY_NEGATIVE','UNARY_NOT',
    'UNARY_INVERT','BINARY_POWER','BINARY_MULTIPLY',
    'BINARY_DIVIDE','BINARY_FLOOR_DIVIDE','BINARY_TRUE_DIVIDE',
    'BINARY_MODULO','BINARY_ADD','BINARY_SUBTRACT',
    'BINARY_LSHIFT','BINARY_RSHIFT','BINARY_AND','BINARY_XOR', 'BINARY_OR',
    'STORE_MAP', 'LOAD_NAME', 'CALL_FUNCTION', 'COMPARE_OP', 'LOAD_ATTR',
    'STORE_NAME', 'GET_ITER', 'FOR_ITER', 'LIST_APPEND', 'JUMP_ABSOLUTE',
    'DELETE_NAME', 'JUMP_IF_TRUE', 'JUMP_IF_FALSE', 'BINARY_SUBSCR',
    ] if x in dis.opmap)


def safe_eval(source, data=None):
    if '__subclasses__' in source:
        raise ValueError('__subclasses__ not allowed')
    c = compile(source, '', 'eval')
    codes = []
    s = c.co_code
    i = 0
    while i < len(s):
        code = ord(s[i])
        codes.append(code)
        if code >= dis.HAVE_ARGUMENT:
            i += 3
        else:
            i += 1
    for code in codes:
        if code not in _ALLOWED_CODES:
            raise ValueError('opcode %s not allowed' % dis.opname[code])
    return eval(c, {'__builtins__': {
        'True': True,
        'False': False,
        'str': str,
        'globals': locals,
        'locals': locals,
        'bool': bool,
        'dict': dict,
        }}, data)
