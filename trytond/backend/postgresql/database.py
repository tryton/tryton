# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time
import logging
import os
import urllib
import json
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

from sql import Flavor
from sql.functions import Function

from trytond.backend.database import DatabaseInterface, SQLType
from trytond.config import config, parse_uri
from trytond.protocols.jsonrpc import JSONDecoder

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError']

logger = logging.getLogger(__name__)

os.environ['PGTZ'] = os.environ.get('TZ', '')


def unescape_quote(s):
    if s.startswith('"') and s.endswith('"'):
        return s.strip('"').replace('""', '"')
    return s


def replace_special_values(s, **mapping):
    for name, value in mapping.iteritems():
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


class Database(DatabaseInterface):

    _lock = RLock()
    _databases = {}
    _connpool = None
    _list_cache = None
    _list_cache_timestamp = None
    _version_cache = {}
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
            if name in cls._databases:
                return cls._databases[name]
            inst = DatabaseInterface.__new__(cls, name=name)

            logger.info('connect to "%s"', name)
            minconn = config.getint('database', 'minconn', default=1)
            maxconn = config.getint('database', 'maxconn', default=64)
            inst._connpool = ThreadedConnectionPool(
                minconn, maxconn, cls.dsn(name),
                cursor_factory=LoggingCursor)

            cls._databases[name] = inst
            return inst

    @classmethod
    def dsn(cls, name):
        uri = parse_uri(config.get('database', 'uri'))
        host = uri.hostname and "host=%s" % uri.hostname or ''
        port = uri.port and "port=%s" % uri.port or ''
        name = "dbname=%s" % name
        user = uri.username and "user=%s" % uri.username or ''
        password = ("password=%s" % urllib.unquote_plus(uri.password)
            if uri.password else '')
        return '%s %s %s %s %s' % (host, port, name, user, password)

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
        if autocommit:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        else:
            conn.set_isolation_level(ISOLATION_LEVEL_REPEATABLE_READ)
        if readonly:
            cursor = conn.cursor()
            cursor.execute('SET TRANSACTION READ ONLY')
        return conn

    def put_connection(self, connection, close=False):
        self._connpool.putconn(connection, close=close)

    def close(self):
        with self._lock:
            self._connpool.closeall()
            self._databases.pop(self.name)

    @classmethod
    def create(cls, connection, database_name, template='template0'):
        cursor = connection.cursor()
        cursor.execute('CREATE DATABASE "' + database_name + '" '
            'TEMPLATE "' + template + '" ENCODING \'unicode\'')
        connection.commit()
        cls._list_cache = None

    def drop(self, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('DROP DATABASE "' + database_name + '"')
        self.__class__._list_cache = None

    def get_version(self, connection):
        if self.name not in self._version_cache:
            cursor = connection.cursor()
            cursor.execute('SHOW server_version_num')
            version, = cursor.fetchone()
            major, rest = divmod(int(version), 10000)
            minor, patch = divmod(rest, 100)
            self._version_cache[self.name] = (major, minor, patch)
        return self._version_cache[self.name]

    def list(self):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = self.__class__._list_cache
        if res and abs(self.__class__._list_cache_timestamp - now) < timeout:
            return res

        connection = self.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT datname FROM pg_database '
                'WHERE datistemplate = false ORDER BY datname')
            res = []
            for db_name, in cursor:
                try:
                    with connect(self.dsn(db_name)) as conn:
                        if self._test(conn):
                            res.append(db_name)
                except Exception:
                    continue
        finally:
            self.put_connection(connection)

        self.__class__._list_cache = res
        self.__class__._list_cache_timestamp = now
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

    def test(self):
        connection = self.get_connection()
        is_tryton_database = self._test(connection)
        self.put_connection(connection)
        return is_tryton_database

    @classmethod
    def _test(cls, connection):
        cursor = connection.cursor()
        cursor.execute('SELECT 1 FROM information_schema.tables '
            'WHERE table_name IN %s',
            (('ir_model', 'ir_model_field', 'ir_ui_view', 'ir_ui_menu',
                    'res_user', 'res_group', 'ir_module',
                    'ir_module_dependency', 'ir_translation',
                    'ir_lang'),))
        return len(cursor.fetchall()) != 0

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
