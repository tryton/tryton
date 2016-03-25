# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time
import logging
import re
import os
import urllib
from decimal import Decimal

try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass
from psycopg2 import connect
from psycopg2.pool import ThreadedConnectionPool
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

from sql import Flavor

from trytond.backend.database import DatabaseInterface
from trytond.config import config, parse_uri

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError']

logger = logging.getLogger(__name__)

RE_VERSION = re.compile(r'\S+ (\d+)\.(\d+)')

os.environ['PGTZ'] = os.environ.get('TZ', '')


def unescape_quote(s):
    if s.startswith('"') and s.endswith('"'):
        return s.strip('"').replace('""', '"')
    return s


def replace_special_values(s, **mapping):
    for name, value in mapping.iteritems():
        s = s.replace('$' + name, value)
    return s


class Database(DatabaseInterface):

    _databases = {}
    _connpool = None
    _list_cache = None
    _list_cache_timestamp = None
    _version_cache = {}
    flavor = Flavor(ilike=True)

    def __new__(cls, name='template1'):
        if name in cls._databases:
            return cls._databases[name]
        return DatabaseInterface.__new__(cls, name=name)

    def __init__(self, name='template1'):
        super(Database, self).__init__(name=name)
        self._databases.setdefault(name, self)
        self._search_path = None
        self._current_user = None

    @classmethod
    def dsn(cls, name):
        uri = parse_uri(config.get('database', 'uri'))
        assert uri.scheme == 'postgresql'
        host = uri.hostname and "host=%s" % uri.hostname or ''
        port = uri.port and "port=%s" % uri.port or ''
        name = "dbname=%s" % name
        user = uri.username and "user=%s" % uri.username or ''
        password = ("password=%s" % urllib.unquote_plus(uri.password)
            if uri.password else '')
        return '%s %s %s %s %s' % (host, port, name, user, password)

    def connect(self):
        if self._connpool is not None:
            return self
        logger.info('connect to "%s"', self.name)
        minconn = config.getint('database', 'minconn', default=1)
        maxconn = config.getint('database', 'maxconn', default=64)
        self._connpool = ThreadedConnectionPool(
            minconn, maxconn, self.dsn(self.name))
        return self

    def get_connection(self, autocommit=False, readonly=False):
        if self._connpool is None:
            self.connect()
        conn = self._connpool.getconn()
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
        if self._connpool is None:
            return
        self._connpool.closeall()
        self._connpool = None

    @classmethod
    def create(cls, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('CREATE DATABASE "' + database_name + '" '
            'TEMPLATE template0 ENCODING \'unicode\'')
        connection.commit()
        cls._list_cache = None

    def drop(self, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('DROP DATABASE "' + database_name + '"')
        Database._list_cache = None

    def get_version(self, connection):
        if self.name not in self._version_cache:
            cursor = connection.cursor()
            cursor.execute('SELECT version()')
            version, = cursor.fetchone()
            self._version_cache[self.name] = tuple(map(int,
                RE_VERSION.search(version).groups()))
        return self._version_cache[self.name]

    @staticmethod
    def dump(database_name):
        from trytond.tools import exec_command_pipe

        cmd = ['pg_dump', '--format=c', '--no-owner']
        env = {}
        uri = parse_uri(config.get('database', 'uri'))
        if uri.username:
            cmd.append('--username=' + uri.username)
        if uri.hostname:
            cmd.append('--host=' + uri.hostname)
        if uri.port:
            cmd.append('--port=' + str(uri.port))
        if uri.password:
            # if db_password is set in configuration we should pass
            # an environment variable PGPASSWORD to our subprocess
            # see libpg documentation
            env['PGPASSWORD'] = uri.password
        cmd.append(database_name)

        pipe = exec_command_pipe(*tuple(cmd), env=env)
        pipe.stdin.close()
        data = pipe.stdout.read()
        res = pipe.wait()
        if res:
            raise Exception('Couldn\'t dump database!')
        return data

    @staticmethod
    def restore(database_name, data):
        from trytond.tools import exec_command_pipe

        database = Database().connect()
        connection = database.get_connection(autocommit=True)
        database.create(connection, database_name)
        database.close()

        cmd = ['pg_restore', '--no-owner']
        env = {}
        uri = parse_uri(config.get('database', 'uri'))
        if uri.username:
            cmd.append('--username=' + uri.username)
        if uri.hostname:
            cmd.append('--host=' + uri.hostname)
        if uri.port:
            cmd.append('--port=' + str(uri.port))
        if uri.password:
            env['PGPASSWORD'] = uri.password
        cmd.append('--dbname=' + database_name)
        args2 = tuple(cmd)

        if os.name == "nt":
            tmpfile = (os.environ['TMP'] or 'C:\\') + os.tmpnam()
            with open(tmpfile, 'wb') as fp:
                fp.write(data)
            args2 = list(args2)
            args2.append(' ' + tmpfile)
            args2 = tuple(args2)

        pipe = exec_command_pipe(*args2, env=env)
        if not os.name == "nt":
            pipe.stdin.write(data)
        pipe.stdin.close()
        res = pipe.wait()
        if res:
            raise Exception('Couldn\'t restore database')

        database = Database(database_name).connect()
        cursor = database.get_connection().cursor()
        if not database.test():
            cursor.close()
            database.close()
            raise Exception('Couldn\'t restore database!')
        cursor.close()
        database.close()
        Database._list_cache = None
        return True

    def list(self):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = Database._list_cache
        if res and abs(Database._list_cache_timestamp - now) < timeout:
            return res

        connection = self.get_connection()
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
        self.put_connection(connection)

        Database._list_cache = res
        Database._list_cache_timestamp = now
        return res

    def init(self):
        from trytond.modules import get_module_info

        connection = self.get_connection()
        cursor = connection.cursor()
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        with open(sql_file) as fp:
            for line in fp.read().split(';'):
                if (len(line) > 0) and (not line.isspace()):
                    cursor.execute(line)

        for module in ('ir', 'res'):
            state = 'uninstalled'
            if module in ('ir', 'res'):
                state = 'to install'
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

    def has_constraint(self):
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
