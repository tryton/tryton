#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
"""
Miscelleanous tools used by tryton
"""
import os, time, sys
import inspect
from trytond.config import CONFIG
import subprocess
import zipfile
from trytond.backend import Database
from threading import Lock, local
import smtplib
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import dis
import datetime
from decimal import Decimal
from trytond.const import OPERATORS

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
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    name3 = False
    if subdir == 'modules':
        module_name = name.split(os.sep)[0]
        if module_name in EGG_MODULES:
            epoint = EGG_MODULES[module_name]
            mod_path = os.path.join(epoint.dist.location,
                    *epoint.module_name.split('.')[:-1])
            name3 = os.path.join(mod_path, name)
            if not os.path.isfile(name3):
                # Find module in path
                for path in sys.path:
                    mod_path = os.path.join(path,
                            *epoint.module_name.split('.')[:-1])
                    name3 = os.path.join(mod_path, name)
                    if os.path.isfile(name3):
                        break
                if not os.path.isfile(name3):
                    # When testing modules from setuptools location is the
                    # module directory
                    name3 = os.path.join(os.path.dirname(epoint.dist.location),
                            name)

    if subdir:
        if subdir == 'modules'\
                and (name.startswith('ir' + os.sep) \
                    or name.startswith('workflow' + os.sep) \
                    or name.startswith('res' + os.sep) \
                    or name.startswith('webdav' + os.sep) \
                    or name.startswith('test' + os.sep)):
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
            return open(i, mode)

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
                    cursor.execute('INSERT INTO ir_cache ' \
                            '("timestamp", "name") ' \
                            'VALUES (%s, %s)', (datetime.datetime.now(), name))
            Cache._resets[dbname].clear()
        finally:
            cursor.commit()
            cursor.close()
            Cache._resets_lock.release()

def memoize(maxsize):
    """
    Decorator to 'memoize' a function - caching its results with a
    near LRU implementation.

    The cache keeps a list of keys logicaly separated in 4 segment :

    segment 1 | ...        | segment4
    [k,k,k,k,k,k,k, .. ,k,k,k,k,k,k,k]

    For each segment there is a pointer that loops on it.  When a key
    is accessed from the cache it is promoted to the first segment (at
    the pointer place of segment one), the key under the pointer is
    moved to the next segment, the pointer is then incremented and so
    on. A key that is removed from the last segment is removed from
    the cache.

    :param: maxsize the size of the cache (must be greater than or
    equal to 4)
    """
    assert maxsize >= 4, "Memoize cannot work if maxsize is less than 4"

    def wrap(fct):
        cache = {}
        keys = [None for i in xrange(maxsize)]
        seg_size = maxsize // 4

        pointers = [i * seg_size for i in xrange(4)]
        max_pointers = [(i + 1) * seg_size for i in xrange(3)] + [maxsize]

        def wrapper(*args):
            key = repr(args)
            res = cache.get(key)
            if res:
                pos, res = res
                keys[pos] = None
            else:
                res = fct(*args)

            value = res
            for segment, pointer in enumerate(pointers):
                newkey = keys[pointer]
                keys[pointer] = key
                cache[key] = (pointer, value)

                pointers[segment] = pointer + 1
                if pointers[segment] == max_pointers[segment]:
                    pointers[segment] = segment * seg_size

                if newkey is None:
                    break
                segment, value = cache.pop(newkey)
                key = newkey

            return res

        wrapper.__doc__ = fct.__doc__
        wrapper.__name__ = fct.__name__

        return wrapper
    return wrap

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

    def __init__(self):
        super(LocalDict, self).__init__()
        self._dict = {}

    def __str__(self):
        return str(self._dict)

    def __repr__(self):
        return str(self._dict)

    def clear(self):
        return self._dict.clear()

    def keys(self):
        return self._dict.keys()

    def __setitem__(self, i, y):
        self._dict.__setitem__(i, y)

    def __getitem__(self, i):
        return self._dict.__getitem__(i)

    def copy(self):
        return self._dict.copy()

    def iteritems(self):
        return self._dict.iteritems()

    def iterkeys(self):
        return self._dict.iterkeys()

    def itervalues(self):
        return self._dict.itervalues()

    def pop(self, k, d=None):
        return self._dict.pop(k, d)

    def popitem(self):
        return self._dict.popitem()

    def setdefault(self, k, d=None):
        return self._dict.setdefault(k, d)

    def update(self, E, **F):
        return self._dict.update(E, F)

    def values(self):
        return self._dict.values()

    def get(self, k, d=None):
        return self._dict.get(k, d)

    def has_key(self, k):
        return self._dict.has_key(k)

    def items(self):
        return self._dict.items()

    def __cmp__(self, y):
        return self._dict.__cmp__(y)

    def __contains__(self, k):
        return self._dict.__contains__(k)

    def __delitem__(self, y):
        return self._dict.__delitem__(y)

    def __eq__(self, y):
        return self._dict.__eq__(y)

    def __ge__(self, y):
        return self._dict.__ge__(y)

    def __getitem__(self, y):
        return self._dict.__getitem__(y)

    def __gt__(self, y):
        return self._dict.__gt__(y)

    def __hash__(self):
        return self._dict.__hash__()

    def __iter__(self):
        return self._dict.__iter__()

    def __le__(self, y):
        return self._dict.__le__(y)

    def __len__(self):
        return self._dict.__len__()

    def __lt__(self, y):
        return self._dict.__lt__(y)

    def __ne__(self, y):
        return self._dict.__ne__(y)

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
    'DELETE_NAME', 'JUMP_IF_TRUE', 'JUMP_IF_FALSE', 'JUMP_IF_FALSE_OR_POP',
    'BINARY_SUBSCR',
    ] if x in dis.opmap)

@memoize(1000)
def _compile_source(source):
    comp = compile(source, '', 'eval')
    codes = []
    co_code = comp.co_code
    i = 0
    while i < len(co_code):
        code = ord(co_code[i])
        codes.append(code)
        if code >= dis.HAVE_ARGUMENT:
            i += 3
        else:
            i += 1
    for code in codes:
        if code not in _ALLOWED_CODES:
            raise ValueError('opcode %s not allowed' % dis.opname[code])
    return comp

def safe_eval(source, data=None):
    if '__subclasses__' in source:
        raise ValueError('__subclasses__ not allowed')

    comp = _compile_source(source)
    return eval(comp, {'__builtins__': {
        'True': True,
        'False': False,
        'str': str,
        'globals': locals,
        'locals': locals,
        'bool': bool,
        'dict': dict,
        'round': round,
        'Decimal': Decimal,
        }}, data)

def reduce_domain(domain):
    '''
    Reduce domain
    '''
    if not domain:
        return []
    operator = 'AND'
    if isinstance(domain[0], basestring):
        operator = domain[0]
        domain = domain[1:]
    result = [operator]
    for arg in domain:
        if (isinstance(arg, tuple) or
                (isinstance(arg, list) and
                    len(arg) > 2 and
                    arg[1] in OPERATORS)):
            #clause
            result.append(arg)
        elif isinstance(arg, list) and arg:
            #sub-domain
            sub_domain = reduce_domain(arg)
            sub_operator = sub_domain[0]
            if sub_operator == operator:
                result.extend(sub_domain[1:])
            else:
                result.append(sub_domain)
    return result
