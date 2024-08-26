# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import logging
import os
import time
import warnings
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from itertools import chain, repeat
from threading import RLock

from psycopg2 import Binary, connect
from psycopg2.extensions import (
    ISOLATION_LEVEL_REPEATABLE_READ, UNICODE, AsIs, cursor, register_adapter,
    register_type)
from psycopg2.pool import PoolError, ThreadedConnectionPool
from psycopg2.sql import SQL, Identifier

try:
    from psycopg2.extensions import PYDATE, PYDATETIME, PYINTERVAL, PYTIME
except ImportError:
    PYDATE, PYDATETIME, PYTIME, PYINTERVAL = None, None, None, None
from psycopg2 import DataError as DatabaseDataError
from psycopg2 import IntegrityError as DatabaseIntegrityError
from psycopg2 import InterfaceError
from psycopg2 import OperationalError as DatabaseOperationalError
from psycopg2 import ProgrammingError
from psycopg2.errors import QueryCanceled as DatabaseTimeoutError
from psycopg2.extras import register_default_json, register_default_jsonb
from sql import Cast, Flavor, For, Table
from sql.conditionals import Coalesce
from sql.functions import Function
from sql.operators import BinaryOperator, Concat

from trytond.backend.database import DatabaseInterface, SQLType
from trytond.config import config, parse_uri
from trytond.tools.gevent import is_gevent_monkey_patched

__all__ = [
    'Database',
    'DatabaseIntegrityError', 'DatabaseDataError', 'DatabaseOperationalError',
    'DatabaseTimeoutError']

logger = logging.getLogger(__name__)

os.environ['PGTZ'] = os.environ.get('TZ', '')
_timeout = config.getint('database', 'timeout')
_minconn = config.getint('database', 'minconn', default=1)
_maxconn = config.getint('database', 'maxconn', default=64)
_default_name = config.get('database', 'default_name', default='template1')


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


class ForSkipLocked(For):
    def __str__(self):
        assert not self.nowait, "Can not use both NO WAIT and SKIP LOCKED"
        return super().__str__() + (' SKIP LOCKED' if not self.nowait else '')


class Unaccent(Function):
    __slots__ = ()
    _function = config.get('database', 'unaccent_function', default='unaccent')


class Similarity(Function):
    __slots__ = ()
    _function = config.get(
        'database', 'similarity_function', default='similarity')


class Match(BinaryOperator):
    __slots__ = ()
    _operator = '@@'


class ToTsvector(Function):
    __slots__ = ()
    _function = 'to_tsvector'


class Setweight(Function):
    __slots__ = ()
    _function = 'setweight'


class TsQuery(Function):
    __slots__ = ()


class ToTsQuery(TsQuery):
    __slots__ = ()
    _function = 'to_tsquery'


class PlainToTsQuery(TsQuery):
    __slots__ = ()
    _function = 'plainto_tsquery'


class PhraseToTsQuery(TsQuery):
    __slots__ = ()
    _function = 'phraseto_tsquery'


class WebsearchToTsQuery(TsQuery):
    __slots__ = ()
    _function = 'websearch_to_tsquery'


class TsRank(Function):
    __slots__ = ()
    _function = 'ts_rank'


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

    index_translators = []
    _lock = RLock()
    _databases = defaultdict(dict)
    _connpool = None
    _list_cache = {}
    _list_cache_timestamp = {}
    _search_path = None
    _current_user = None
    _has_returning = None
    _has_select_for_skip_locked = None
    _has_proc = defaultdict(lambda: defaultdict(dict))
    _extensions = defaultdict(dict)
    _search_full_text_languages = defaultdict(dict)
    flavor = Flavor(ilike=True)

    TYPES_MAPPING = {
        'SMALLINT': SQLType('INT2', 'INT2'),
        'BIGINT': SQLType('INT8', 'INT8'),
        'BLOB': SQLType('BYTEA', 'BYTEA'),
        'DATETIME': SQLType('TIMESTAMP', 'TIMESTAMP(0)'),
        'REAL': SQLType('FLOAT4', 'FLOAT4'),
        'FLOAT': SQLType('FLOAT8', 'FLOAT8'),
        'FULLTEXT': SQLType('TSVECTOR', 'TSVECTOR'),
        'INTEGER': SQLType('INT4', 'INT4'),
        'JSON': SQLType('JSONB', 'JSONB'),
        'TIMESTAMP': SQLType('TIMESTAMP', 'TIMESTAMP(6)'),
        }

    def __new__(cls, name=_default_name):
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
                inst = DatabaseInterface.__new__(cls, name=name)
                try:
                    inst._connpool = ThreadedConnectionPool(
                        _minconn, _maxconn, **cls._connection_params(name),
                        cursor_factory=LoggingCursor)
                except Exception:
                    logger.error(
                        'connection to "%s" failed', name, exc_info=True)
                    raise
                else:
                    logger.info('connection to "%s" succeeded', name)
                databases[name] = inst
            inst._last_use = datetime.now()
            return inst

    def __init__(self, name=_default_name):
        super(Database, self).__init__(name)

    @classmethod
    def _connection_params(cls, name):
        uri = parse_uri(config.get('database', 'uri'))
        if uri.path and uri.path != '/':
            warnings.warn("The path specified in the URI will be overridden")
        params = {
            'dsn': uri._replace(path=name).geturl(),
            'fallback_application_name': os.environ.get(
                'TRYTOND_APPNAME', 'trytond'),
            }
        return params

    def connect(self):
        return self

    def get_connection(
            self, autocommit=False, readonly=False, statement_timeout=None):
        retry = max(config.getint('database', 'retry'), _maxconn)
        for count in range(retry, -1, -1):
            try:
                conn = self._connpool.getconn()
            except (PoolError, DatabaseOperationalError):
                if count and not self._connpool.closed:
                    logger.info('waiting a connection')
                    time.sleep(1)
                    continue
                raise
            except Exception:
                logger.error(
                    'connection to "%s" failed', self.name, exc_info=True)
                raise
            try:
                conn.set_session(
                    isolation_level=ISOLATION_LEVEL_REPEATABLE_READ,
                    readonly=readonly,
                    autocommit=autocommit)
                with conn.cursor() as cur:
                    if statement_timeout:
                        cur.execute('SET statement_timeout=%s' %
                            (statement_timeout * 1000))
                    else:
                        # Detect disconnection
                        cur.execute('SELECT 1')
            except DatabaseOperationalError:
                self._connpool.putconn(conn, close=True)
                continue
            break
        return conn

    def put_connection(self, connection, close=False):
        try:
            connection.reset()
        except InterfaceError:
            pass
        self._connpool.putconn(connection, close=close)

    def close(self):
        with self._lock:
            logger.info('disconnection from "%s"', self.name)
            self._connpool.closeall()
            self._databases[os.getpid()].pop(self.name)

    @classmethod
    def create(cls, connection, database_name, template='template0'):
        cursor = connection.cursor()
        cursor.execute(
            SQL(
                "CREATE DATABASE {} TEMPLATE {} ENCODING 'unicode'")
            .format(
                Identifier(database_name),
                Identifier(template)))
        connection.commit()
        cls._list_cache.clear()

    @classmethod
    def drop(cls, connection, database_name):
        cursor = connection.cursor()
        cursor.execute(SQL("DROP DATABASE {}")
            .format(Identifier(database_name)))
        cls._list_cache.clear()
        cls._has_proc.pop(database_name, None)
        cls._search_full_text_languages.pop(database_name, None)

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
                    logger.debug(
                        'Test failed for "%s"', db_name, exc_info=True)
                    continue
        finally:
            self.put_connection(connection, close=True)

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

            for module in ['ir', 'res']:
                info = get_module_info(module)
                cursor.execute('INSERT INTO ir_module '
                    '(create_uid, create_date, name, state) '
                    'VALUES (%s, now(), %s, %s) '
                    'RETURNING id',
                    (0, module, 'to activate'))
                module_id = cursor.fetchone()[0]
                for dependency in info.get('depends', []):
                    cursor.execute('INSERT INTO ir_module_dependency '
                        '(create_uid, create_date, module, name) '
                        'VALUES (%s, now(), %s, %s)',
                        (0, module_id, dependency))

            connection.commit()
        finally:
            self.put_connection(connection)

    def test(self, hostname=None):
        try:
            connection = self.get_connection()
        except Exception:
            logger.debug('Test failed for "%s"', self.name, exc_info=True)
            return False
        try:
            return self._test(connection, hostname=hostname)
        finally:
            self.put_connection(connection, close=True)

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
            try:
                cursor.execute(
                    'SELECT hostname FROM ir_configuration')
                hostnames = {h for h, in cursor if h}
                if hostnames and hostname not in hostnames:
                    return False
            except ProgrammingError:
                pass
        return True

    def nextid(self, connection, table, count=1):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence(format(%s, %s), %s)) "
            "FROM generate_series(1, %s)",
            ('%I', table, 'id', count))
        if count == 1:
            return cursor.fetchone()[0]
        else:
            return [id for id, in cursor]

    def setnextid(self, connection, table, value):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence(format(%s, %s), %s), %s)",
            ('%I', table, 'id', value))

    def currid(self, connection, table):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pg_get_serial_sequence(format(%s, %s), %s)",
            ('%I', table, 'id'))
        sequence_name, = cursor.fetchone()
        cursor.execute(f"SELECT last_value FROM {sequence_name}")
        return cursor.fetchone()[0]

    def lock(self, connection, table):
        cursor = connection.cursor()
        cursor.execute(SQL('LOCK {} IN EXCLUSIVE MODE NOWAIT').format(
                Identifier(table)))

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

    def get_select_for_skip_locked(self):
        if self._has_select_for_skip_locked is None:
            connection = self.get_connection()
            try:
                # SKIP LOCKED clause is available since PostgreSQL 9.5
                self._has_select_for_skip_locked = (
                    self.get_version(connection) >= (9, 5))
            finally:
                self.put_connection(connection)
        if self._has_select_for_skip_locked:
            return ForSkipLocked
        else:
            return For

    def has_window_functions(self):
        return True

    @classmethod
    def has_sequence(cls):
        return True

    def has_proc(self, name, property='oid'):
        if (name in self._has_proc[self.name]
                and property in self._has_proc[self.name][name]):
            return self._has_proc[self.name][name][property]
        connection = self.get_connection()
        result = False
        try:
            cursor = connection.cursor()
            cursor.execute(
                SQL('SELECT {} FROM pg_proc WHERE proname=%s').format(
                    Identifier(property)), (name,))
            result = cursor.fetchone()
            if result:
                result, = result
        finally:
            self.put_connection(connection)
        self._has_proc[self.name][name][property] = result
        return result

    def has_unaccent(self):
        return self.has_proc(Unaccent._function)

    def has_unaccent_indexable(self):
        return self.has_proc(Unaccent._function, 'provolatile') == 'i'

    def has_similarity(self):
        return self.has_proc(Similarity._function)

    def similarity(self, column, value):
        return Similarity(column, value)

    def has_search_full_text(self):
        return True

    def _search_full_text_language(self, language):
        languages = self._search_full_text_languages[self.name]
        if language not in languages:
            lang = Table('ir_lang')
            connection = self.get_connection()
            try:
                cursor = connection.cursor()
                cursor.execute(*lang.select(
                        Coalesce(lang.pg_text_search, 'simple'),
                        where=lang.code == language,
                        limit=1))
                config_name, = cursor.fetchone()
            finally:
                self.put_connection(connection)
            languages[language] = config_name
        else:
            config_name = languages[language]
        return config_name

    def format_full_text(self, *documents, language=None):
        size = max(len(documents) // 4, 1)
        if len(documents) > 1:
            weights = chain(
                ['A'] * size, ['B'] * size, ['C'] * size, repeat('D'))
        else:
            weights = [None]
        expression = None
        if language:
            config_name = self._search_full_text_language(language)
        else:
            config_name = None
        for document, weight in zip(documents, weights):
            if not document:
                continue
            if config_name:
                ts_vector = ToTsvector(config_name, document)
            else:
                ts_vector = ToTsvector('simple', document)
            if weight:
                ts_vector = Setweight(ts_vector, weight)
            if expression is None:
                expression = ts_vector
            else:
                expression = Concat(expression, ts_vector)
        return expression

    def format_full_text_query(self, query, language=None):
        connection = self.get_connection()
        try:
            version = self.get_version(connection)
        finally:
            self.put_connection(connection)
        if not isinstance(query, TsQuery):
            if version >= (11, 0):
                ToTsQuery = WebsearchToTsQuery
            else:
                ToTsQuery = PlainToTsQuery
            if language:
                config_name = self._search_full_text_language(language)
            else:
                config_name = 'simple'
            query = ToTsQuery(config_name, query)
        return query

    def search_full_text(self, document, query):
        return Match(document, query)

    def rank_full_text(self, document, query, normalize=None):
        # TODO: weights and cover density
        norm_int = 0
        if normalize:
            values = {
                'document log': 1,
                'document': 2,
                'mean': 4,
                'word': 8,
                'word log': 16,
                'rank': 32,
                }
            for norm in normalize:
                norm_int |= values.get(norm, 0)
        return TsRank(document, query, norm_int)

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

        cursor.execute(
            SQL("CREATE SEQUENCE {} INCREMENT BY %s START WITH %s").format(
                Identifier(name)),
            (number_increment, start_value))

    def sequence_update(
            self, connection, name, number_increment=1, start_value=1):
        cursor = connection.cursor()
        cursor.execute(
            SQL("ALTER SEQUENCE {} INCREMENT BY %s RESTART WITH %s").format(
                Identifier(name)),
            (number_increment, start_value))

    def sequence_rename(self, connection, old_name, new_name):
        cursor = connection.cursor()
        if (self.sequence_exist(connection, old_name)
                and not self.sequence_exist(connection, new_name)):
            cursor.execute(
                SQL("ALTER TABLE {} RENAME TO {}").format(
                    Identifier(old_name),
                    Identifier(new_name)))

    def sequence_delete(self, connection, name):
        cursor = connection.cursor()
        cursor.execute(SQL("DROP SEQUENCE {}").format(
                Identifier(name)))

    def sequence_next_number(self, connection, name):
        cursor = connection.cursor()
        version = self.get_version(connection)
        if version >= (10, 0):
            cursor.execute(
                'SELECT increment_by '
                'FROM pg_sequences '
                'WHERE sequencename=%s',
                (name,))
            increment, = cursor.fetchone()
            cursor.execute(
                SQL(
                    'SELECT CASE WHEN NOT is_called THEN last_value '
                    'ELSE last_value + %s '
                    'END '
                    'FROM {}').format(Identifier(name)),
                (increment,))
        else:
            cursor.execute(
                SQL(
                    'SELECT CASE WHEN NOT is_called THEN last_value '
                    'ELSE last_value + increment_by '
                    'END '
                    'FROM {}').format(Identifier(name)))
        return cursor.fetchone()[0]

    def has_channel(self):
        return True

    def has_extension(self, extension_name):
        if extension_name in self._extensions[self.name]:
            return self._extensions[self.name][extension_name]

        connection = self.get_connection()
        result = False
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname=%s",
                (extension_name,))
            result = bool(cursor.rowcount)
        finally:
            self.put_connection(connection)
        self._extensions[self.name][extension_name] = result
        return result

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
    from trytond.protocols.jsonrpc import JSONDecoder
    return json.loads(value, object_hook=JSONDecoder())


register_default_json(loads=convert_json)
register_default_jsonb(loads=convert_json)

if is_gevent_monkey_patched():
    from psycopg2.extensions import set_wait_callback
    from psycopg2.extras import wait_select
    set_wait_callback(wait_select)
