# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
import time
import logging
import os
import urllib.request, urllib.parse, urllib.error
import json
from datetime import datetime
from decimal import Decimal
from threading import RLock

try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass
from psycopg2 import connect, Binary
from psycopg2.pool import ThreadedConnectionPool, PoolError
from psycopg2.extensions import cursor
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import register_type, register_adapter
from psycopg2.extensions import UNICODE, AsIs
try:
    from psycopg2.extensions import PYDATE, PYDATETIME, PYTIME, PYINTERVAL
except ImportError:
    PYDATE, PYDATETIME, PYTIME, PYINTERVAL = None, None, None, None
from psycopg2 import IntegrityError as DatabaseIntegrityError
from psycopg2 import OperationalError as DatabaseOperationalError
from psycopg2.extras import register_default_json, register_default_jsonb

from sql import Flavor, Cast
from sql.functions import Function
from sql.operators import BinaryOperator

from trytond.backend.database import DatabaseInterface, SQLType
from trytond.config import config, parse_uri
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.tools.gevent import is_gevent_monkey_patched

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError']

logger = logging.getLogger(__name__)

os.environ['PGTZ'] = os.environ.get('TZ', '')
_timeout = config.getint('database', 'timeout')
_minconn = config.getint('database', 'minconn', default=1)
_maxconn = config.getint('database', 'maxconn', default=64)


def unescape_quote(s):
    if s.startswith('"') and s.endswith('"'):
        return s.strip('"').replace('""', '"')
    return s


def replace_special_values(s, **mapping):
    for name, value in mapping.items():
        s = s.replace('$' + name, value)
    return s


class LoggingCursor(cursor):
    def execute(self, sql, args=None):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(self.mogrify(sql, args))
        cursor.execute(self, sql, args)


class Unaccent(Function):
    __slots__ = ()
    _function = 'unaccent'


class AdvisoryLock(Function):
    _function = 'pg_advisory_xact_lock'


class TryAdvisoryLock(Function):
    _function = 'pg_try_advisory_xact_lock'


class JSONBExtractPath(Function):
    __slots__ = ()
    _function = 'jsonb_extract_path'


class JSONKeyExists(BinaryOperator):
    __slots__ = ()
    _operator = '?'


class _BinaryOperatorArray(BinaryOperator):
    "Binary Operator that convert list into Array"

    @property
    def _operands(self):
        if isinstance(self.right, list):
            return (self.left, None)
        return super()._operands

    @property
    def params(self):
        params = super().params
        if isinstance(self.right, list):
            params = params[:-1] + (self.right,)
        return params


class JSONAnyKeyExist(_BinaryOperatorArray):
    __slots__ = ()
    _operator = '?|'


class JSONAllKeyExist(_BinaryOperatorArray):
    __slots__ = ()
    _operator = '?&'


class JSONContains(BinaryOperator):
    __slots__ = ()
    _operator = '@>'


class Database(DatabaseInterface):

    _lock = RLock()
    _databases = defaultdict(dict)
    _connpool = None
    _list_cache = {}
    _list_cache_timestamp = {}
    _search_path = None
    _current_user = None
    _has_returning = None
    _has_unaccent = {}
    flavor = Flavor(ilike=True)

    TYPES_MAPPING = {
        'INTEGER': SQLType('INT4', 'INT4'),
        'BIGINT': SQLType('INT8', 'INT8'),
        'FLOAT': SQLType('FLOAT8', 'FLOAT8'),
        'BLOB': SQLType('BYTEA', 'BYTEA'),
        'DATETIME': SQLType('TIMESTAMP', 'TIMESTAMP(0)'),
        'TIMESTAMP': SQLType('TIMESTAMP', 'TIMESTAMP(6)'),
        }

    def __new__(cls, name='template1'):
        with cls._lock:
            now = datetime.now()
            databases = cls._databases[os.getpid()]
            for database in list(databases.values()):
                if ((now - database._last_use).total_seconds() > _timeout
                        and database.name != name
                        and not database._connpool._used):
                    database.close()
            if name in databases:
                inst = databases[name]
            else:
                if name == 'template1':
                    minconn = 0
                else:
                    minconn = _minconn
                inst = DatabaseInterface.__new__(cls, name=name)
                logger.info('connect to "%s"', name)
                inst._connpool = ThreadedConnectionPool(
                    minconn, _maxconn, **cls._connection_params(name),
                    cursor_factory=LoggingCursor)
                databases[name] = inst
            inst._last_use = datetime.now()
            return inst

    def __init__(self, name='template1'):
        super(Database, self).__init__(name)

    @classmethod
    def _connection_params(cls, name):
        uri = parse_uri(config.get('database', 'uri'))
        params = {
            'dbname': name,
            }
        if uri.username:
            params['user'] = uri.username
        if uri.password:
            params['password'] = urllib.parse.unquote_plus(uri.password)
        if uri.hostname:
            params['host'] = uri.hostname
        if uri.port:
            params['port'] = uri.port
        return params

    def connect(self):
        return self

    def get_connection(self, autocommit=False, readonly=False):
        for count in range(config.getint('database', 'retry'), -1, -1):
            try:
                conn = self._connpool.getconn()
                break
            except PoolError:
                if count and not self._connpool.closed:
                    logger.info('waiting a connection')
                    time.sleep(1)
                    continue
                raise
        # We do not use set_session because psycopg2 < 2.7 and psycopg2cffi
        # change the default_transaction_* attributes which breaks external
        # pooling at the transaction level.
        if autocommit:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        else:
            conn.set_isolation_level(ISOLATION_LEVEL_REPEATABLE_READ)
        # psycopg2cffi does not have the readonly property
        if hasattr(conn, 'readonly'):
            conn.readonly = readonly
        elif not autocommit and readonly:
            cursor = conn.cursor()
            cursor.execute('SET TRANSACTION READ ONLY')
        return conn

    def put_connection(self, connection, close=False):
        self._connpool.putconn(connection, close=close)

    def close(self):
        with self._lock:
            logger.info('disconnect from "%s"', self.name)
            self._connpool.closeall()
            self._databases[os.getpid()].pop(self.name)

    @classmethod
    def create(cls, connection, database_name, template='template0'):
        cursor = connection.cursor()
        cursor.execute('CREATE DATABASE "' + database_name + '" '
            'TEMPLATE "' + template + '" ENCODING \'unicode\'')
        connection.commit()
        cls._list_cache.clear()

    def drop(self, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('DROP DATABASE "' + database_name + '"')
        self.__class__._list_cache.clear()

    def get_version(self, connection):
        version = connection.server_version
        major, rest = divmod(int(version), 10000)
        minor, patch = divmod(rest, 100)
        return (major, minor, patch)

    def list(self, hostname=None):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = self.__class__._list_cache.get(hostname)
        timestamp = self.__class__._list_cache_timestamp.get(hostname, now)
        if res and abs(timestamp - now) < timeout:
            return res

        connection = self.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT datname FROM pg_database '
                'WHERE datistemplate = false ORDER BY datname')
            res = []
            for db_name, in cursor:
                try:
                    conn = connect(**self._connection_params(db_name))
                    try:
                        with conn:
                            if self._test(conn, hostname=hostname):
                                res.append(db_name)
                    finally:
                        conn.close()
                except Exception:
                    continue
        finally:
            self.put_connection(connection)

        self.__class__._list_cache[hostname] = res
        self.__class__._list_cache_timestamp[hostname] = now
        return res

    def init(self):
        from trytond.modules import get_module_info

        connection = self.get_connection()
        try:
            cursor = connection.cursor()
            sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
            with open(sql_file) as fp:
                for line in fp.read().split(';'):
                    if (len(line) > 0) and (not line.isspace()):
                        cursor.execute(line)

            for module in ('ir', 'res'):
                state = 'not activated'
                if module in ('ir', 'res'):
                    state = 'to activate'
                info = get_module_info(module)
                cursor.execute('SELECT NEXTVAL(\'ir_module_id_seq\')')
                module_id = cursor.fetchone()[0]
                cursor.execute('INSERT INTO ir_module '
                    '(id, create_uid, create_date, name, state) '
                    'VALUES (%s, %s, now(), %s, %s)',
                    (module_id, 0, module, state))
                for dependency in info.get('depends', []):
                    cursor.execute('INSERT INTO ir_module_dependency '
                        '(create_uid, create_date, module, name) '
                        'VALUES (%s, now(), %s, %s)',
                        (0, module_id, dependency))

            connection.commit()
        finally:
            self.put_connection(connection)

    def test(self, hostname=None):
        connection = self.get_connection()
        try:
            is_tryton_database = self._test(connection, hostname=hostname)
        except Exception:
            is_tryton_database = False
        finally:
            self.put_connection(connection)
        return is_tryton_database

    @classmethod
    def _test(cls, connection, hostname=None):
        cursor = connection.cursor()
        tables = ('ir_model', 'ir_model_field', 'ir_ui_view', 'ir_ui_menu',
            'res_user', 'res_group', 'ir_module', 'ir_module_dependency',
            'ir_translation', 'ir_lang', 'ir_configuration')
        cursor.execute('SELECT table_name FROM information_schema.tables '
            'WHERE table_name IN %s', (tables,))
        if len(cursor.fetchall()) != len(tables):
            return False
        if hostname:
            cursor.execute(
                'SELECT hostname FROM ir_configuration')
            hostnames = {h for h, in cursor.fetchall() if h}
            if hostnames and hostname not in hostnames:
                return False
        return True

    def nextid(self, connection, table):
        cursor = connection.cursor()
        cursor.execute("SELECT NEXTVAL('" + table + "_id_seq')")
        return cursor.fetchone()[0]

    def setnextid(self, connection, table, value):
        cursor = connection.cursor()
        cursor.execute("SELECT SETVAL('" + table + "_id_seq', %d)" % value)

    def currid(self, connection, table):
        cursor = connection.cursor()
        cursor.execute('SELECT last_value FROM "' + table + '_id_seq"')
        return cursor.fetchone()[0]

    def lock(self, connection, table):
        cursor = connection.cursor()
        cursor.execute('LOCK "%s" IN EXCLUSIVE MODE NOWAIT' % table)

    def lock_id(self, id, timeout=None):
        if not timeout:
            return TryAdvisoryLock(id)
        else:
            return AdvisoryLock(id)

    def has_constraint(self, constraint):
        return True

    def has_multirow_insert(self):
        return True

    def get_table_schema(self, connection, table_name):
        cursor = connection.cursor()
        for schema in self.search_path:
            cursor.execute('SELECT 1 '
                'FROM information_schema.tables '
                'WHERE table_name = %s AND table_schema = %s',
                (table_name, schema))
            if cursor.rowcount:
                return schema

    @property
    def current_user(self):
        if self._current_user is None:
            connection = self.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute('SELECT current_user')
                self._current_user = cursor.fetchone()[0]
            finally:
                self.put_connection(connection)
        return self._current_user

    @property
    def search_path(self):
        if self._search_path is None:
            connection = self.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute('SHOW search_path')
                path, = cursor.fetchone()
                special_values = {
                    'user': self.current_user,
                }
                self._search_path = [
                    unescape_quote(replace_special_values(
                            p.strip(), **special_values))
                    for p in path.split(',')]
            finally:
                self.put_connection(connection)
        return self._search_path

    def has_returning(self):
        if self._has_returning is None:
            connection = self.get_connection()
            try:
                # RETURNING clause is available since PostgreSQL 8.2
                self._has_returning = self.get_version(connection) >= (8, 2)
            finally:
                self.put_connection(connection)
        return self._has_returning

    def has_select_for(self):
        return True

    def has_window_functions(self):
        return True

    @classmethod
    def has_sequence(cls):
        return True

    def has_unaccent(self):
        if self.name in self._has_unaccent:
            return self._has_unaccent[self.name]
        connection = self.get_connection()
        unaccent = False
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_proc WHERE proname=%s",
                (Unaccent._function,))
            unaccent = bool(cursor.rowcount)
        finally:
            self.put_connection(connection)
        self._has_unaccent[self.name] = unaccent
        return unaccent

    def sql_type(self, type_):
        if type_ in self.TYPES_MAPPING:
            return self.TYPES_MAPPING[type_]
        if type_.startswith('VARCHAR'):
            return SQLType('VARCHAR', type_)
        return SQLType(type_, type_)

    def sql_format(self, type_, value):
        if type_ == 'BLOB':
            if value is not None:
                return Binary(value)
        return value

    def unaccent(self, value):
        if self.has_unaccent():
            return Unaccent(value)
        return value

    def sequence_exist(self, connection, name):
        cursor = connection.cursor()
        for schema in self.search_path:
            cursor.execute('SELECT 1 '
                'FROM information_schema.sequences '
                'WHERE sequence_name = %s AND sequence_schema = %s',
                (name, schema))
            if cursor.rowcount:
                return True
        return False

    def sequence_create(
            self, connection, name, number_increment=1, start_value=1):
        cursor = connection.cursor()

        param = self.flavor.param
        cursor.execute(
            'CREATE SEQUENCE "%s" '
            'INCREMENT BY %s '
            'START WITH %s'
            % (name, param, param),
            (number_increment, start_value))

    def sequence_update(
            self, connection, name, number_increment=1, start_value=1):
        cursor = connection.cursor()
        param = self.flavor.param
        cursor.execute(
            'ALTER SEQUENCE "%s" '
            'INCREMENT BY %s '
            'RESTART WITH %s'
            % (name, param, param),
            (number_increment, start_value))

    def sequence_rename(self, connection, old_name, new_name):
        cursor = connection.cursor()
        if (self.sequence_exist(connection, old_name)
                and not self.sequence_exist(connection, new_name)):
            cursor.execute('ALTER TABLE "%s" RENAME TO "%s"'
                % (old_name, new_name))

    def sequence_delete(self, connection, name):
        cursor = connection.cursor()
        cursor.execute('DROP SEQUENCE "%s"' % name)

    def sequence_next_number(self, connection, name):
        cursor = connection.cursor()
        version = self.get_version(connection)
        if version >= (10, 0):
            cursor.execute(
                'SELECT increment_by '
                'FROM pg_sequences '
                'WHERE sequencename=%s '
                % self.flavor.param,
                (name,))
            increment, = cursor.fetchone()
            cursor.execute(
                'SELECT CASE WHEN NOT is_called THEN last_value '
                            'ELSE last_value + %s '
                        'END '
                'FROM "%s"' % (self.flavor.param, name),
                (increment,))
        else:
            cursor.execute(
                'SELECT CASE WHEN NOT is_called THEN last_value '
                            'ELSE last_value + increment_by '
                       'END '
                'FROM "%s"' % name)
        return cursor.fetchone()[0]

    def has_channel(self):
        return True

    def json_get(self, column, key=None):
        column = Cast(column, 'jsonb')
        if key:
            column = JSONBExtractPath(column, key)
        return column

    def json_key_exists(self, column, key):
        return JSONKeyExists(Cast(column, 'jsonb'), key)

    def json_any_keys_exist(self, column, keys):
        return JSONAnyKeyExist(Cast(column, 'jsonb'), keys)

    def json_all_keys_exist(self, column, keys):
        return JSONAllKeyExist(Cast(column, 'jsonb'), keys)

    def json_contains(self, column, json):
        return JSONContains(Cast(column, 'jsonb'), Cast(json, 'jsonb'))


register_type(UNICODE)
if PYDATE:
    register_type(PYDATE)
if PYDATETIME:
    register_type(PYDATETIME)
if PYTIME:
    register_type(PYTIME)
if PYINTERVAL:
    register_type(PYINTERVAL)
register_adapter(float, lambda value: AsIs(repr(value)))
register_adapter(Decimal, lambda value: AsIs(str(value)))


def convert_json(value):
    return json.loads(value, object_hook=JSONDecoder())
register_default_json(loads=convert_json)
register_default_jsonb(loads=convert_json)

if is_gevent_monkey_patched():
    from psycopg2.extensions import set_wait_callback
    from psycopg2.extras import wait_select
    set_wait_callback(wait_select)
