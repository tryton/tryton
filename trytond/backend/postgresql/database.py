#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import config, parse_uri
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import cursor as PsycopgCursor
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import register_type, register_adapter
from psycopg2.extensions import UNICODE, AsIs
try:
    from psycopg2.extensions import PYDATE, PYDATETIME, PYTIME
except ImportError:
    PYDATE, PYDATETIME, PYTIME = None, None, None
from psycopg2 import IntegrityError as DatabaseIntegrityError
from psycopg2 import OperationalError as DatabaseOperationalError
import time
import logging
import re
import os
import urllib
if os.name == 'posix':
    import pwd
from decimal import Decimal
from sql import Flavor

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError',
    'Cursor']

RE_VERSION = re.compile(r'\S+ (\d+)\.(\d+)')

os.environ['PGTZ'] = os.environ.get('TZ', '')


class Database(DatabaseInterface):

    _databases = {}
    _connpool = None
    _list_cache = None
    _list_cache_timestamp = None
    _version_cache = {}
    flavor = Flavor(ilike=True)

    def __new__(cls, database_name='template1'):
        if database_name in cls._databases:
            return cls._databases[database_name]
        return DatabaseInterface.__new__(cls, database_name=database_name)

    def __init__(self, database_name='template1'):
        super(Database, self).__init__(database_name=database_name)
        self._databases.setdefault(database_name, self)

    def connect(self):
        if self._connpool is not None:
            return self
        logger = logging.getLogger('database')
        logger.info('connect to "%s"' % self.database_name)
        uri = parse_uri(config.get('database', 'uri'))
        assert uri.scheme == 'postgresql'
        host = uri.hostname and "host=%s" % uri.hostname or ''
        port = uri.port and "port=%s" % uri.port or ''
        name = "dbname=%s" % self.database_name
        user = uri.username and "user=%s" % uri.username or ''
        password = ("password=%s" % urllib.unquote_plus(uri.password)
            if uri.password else '')
        minconn = config.getint('database', 'minconn', 1)
        maxconn = config.getint('database', 'maxconn', 64)
        dsn = '%s %s %s %s %s' % (host, port, name, user, password)
        self._connpool = ThreadedConnectionPool(minconn, maxconn, dsn)
        return self

    def cursor(self, autocommit=False, readonly=False):
        if self._connpool is None:
            self.connect()
        conn = self._connpool.getconn()
        if autocommit:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        else:
            conn.set_isolation_level(ISOLATION_LEVEL_REPEATABLE_READ)
        cursor = Cursor(self._connpool, conn, self)
        if readonly:
            cursor.execute('SET TRANSACTION READ ONLY')
        return cursor

    def close(self):
        if self._connpool is None:
            return
        self._connpool.closeall()
        self._connpool = None

    @classmethod
    def create(cls, cursor, database_name):
        cursor.execute('CREATE DATABASE "' + database_name + '" '
            'TEMPLATE template0 ENCODING \'unicode\'')
        cls._list_cache = None

    @classmethod
    def drop(cls, cursor, database_name):
        cursor.execute('DROP DATABASE "' + database_name + '"')
        cls._list_cache = None

    def get_version(self, cursor):
        if self.database_name not in self._version_cache:
            cursor.execute('SELECT version()')
            version, = cursor.fetchone()
            self._version_cache[self.database_name] = tuple(map(int,
                RE_VERSION.search(version).groups()))
        return self._version_cache[self.database_name]

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
        cursor = database.cursor(autocommit=True)
        database.create(cursor, database_name)
        cursor.commit()
        cursor.close()
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
        cursor = database.cursor()
        if not cursor.test():
            cursor.close()
            database.close()
            raise Exception('Couldn\'t restore database!')
        cursor.close()
        database.close()
        Database._list_cache = None
        return True

    @staticmethod
    def list(cursor):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = Database._list_cache
        if res and abs(Database._list_cache_timestamp - now) < timeout:
            return res
        uri = parse_uri(config.get('database', 'uri'))
        db_user = uri.username or os.environ.get('PGUSER')
        if not db_user and os.name == 'posix':
            db_user = pwd.getpwuid(os.getuid())[0]
        if db_user:
            cursor.execute("SELECT datname "
                "FROM pg_database "
                "WHERE datdba = ("
                    "SELECT usesysid "
                    "FROM pg_user "
                    "WHERE usename=%s) "
                    "AND datname not in "
                        "('template0', 'template1', 'postgres') "
                "ORDER BY datname",
                (db_user,))
        else:
            cursor.execute("SELECT datname "
                "FROM pg_database "
                "WHERE datname not in "
                    "('template0', 'template1','postgres') "
                "ORDER BY datname")
        res = []
        for db_name, in cursor.fetchall():
            db_name = db_name.encode('utf-8')
            try:
                database = Database(db_name).connect()
            except Exception:
                continue
            cursor2 = database.cursor()
            if cursor2.test():
                res.append(db_name)
                cursor2.close(close=True)
            else:
                cursor2.close(close=True)
                database.close()
        Database._list_cache = res
        Database._list_cache_timestamp = now
        return res

    @staticmethod
    def init(cursor):
        from trytond.modules import get_module_info
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        with open(sql_file) as fp:
            for line in fp.read().split(';'):
                if (len(line) > 0) and (not line.isspace()):
                    cursor.execute(line)

        for module in ('ir', 'res', 'webdav'):
            state = 'uninstalled'
            if module in ('ir', 'res'):
                state = 'to install'
            info = get_module_info(module)
            cursor.execute('SELECT NEXTVAL(\'ir_module_module_id_seq\')')
            module_id = cursor.fetchone()[0]
            cursor.execute('INSERT INTO ir_module_module '
                '(id, create_uid, create_date, name, state) '
                'VALUES (%s, %s, now(), %s, %s)',
                (module_id, 0, module, state))
            for dependency in info.get('depends', []):
                cursor.execute('INSERT INTO ir_module_module_dependency '
                    '(create_uid, create_date, module, name) '
                    'VALUES (%s, now(), %s, %s)',
                    (0, module_id, dependency))


class _Cursor(PsycopgCursor):

    def __build_dict(self, row):
        return dict((desc[0], row[i])
                for i, desc in enumerate(self.description))

    def dictfetchone(self):
        row = self.fetchone()
        if row:
            return self.__build_dict(row)
        else:
            return row

    def dictfetchmany(self, size):
        rows = self.fetchmany(size)
        return [self.__build_dict(row) for row in rows]

    def dictfetchall(self):
        rows = self.fetchall()
        return [self.__build_dict(row) for row in rows]


class Cursor(CursorInterface):

    def __init__(self, connpool, conn, database):
        super(Cursor, self).__init__()
        self._connpool = connpool
        self._conn = conn
        self._database = database
        self.cursor = conn.cursor(cursor_factory=_Cursor)
        self.commit()
        self.sql_from_log = {}
        self.sql_into_log = {}
        self.count = {
            'from': 0,
            'into': 0,
        }

    @property
    def database_name(self):
        return self._database.database_name

    # TODO to remove
    @property
    def dbname(self):
        return self.database_name

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        if params:
            return self.cursor.execute(sql, params)
        else:
            return self.cursor.execute(sql)

    def close(self, close=False):
        self.cursor.close()
        self.rollback()
        self._connpool.putconn(self._conn, close=close)

    def commit(self):
        super(Cursor, self).commit()
        self._conn.commit()

    def rollback(self):
        super(Cursor, self).rollback()
        self._conn.rollback()

    def test(self):
        self.cursor.execute("SELECT relname "
            "FROM pg_class "
            "WHERE relkind = 'r' AND relname in ("
                "'ir_model', "
                "'ir_model_field', "
                "'ir_ui_view', "
                "'ir_ui_menu', "
                "'res_user', "
                "'res_group', "
                "'ir_module_module', "
                "'ir_module_module_dependency', "
                "'ir_translation', "
                "'ir_lang'"
                ")")
        return len(self.cursor.fetchall()) != 0

    def nextid(self, table):
        self.cursor.execute("SELECT NEXTVAL('" + table + "_id_seq')")
        return self.cursor.fetchone()[0]

    def setnextid(self, table, value):
        self.cursor.execute("SELECT SETVAL('" + table + "_id_seq', %d)"
            % value)

    def currid(self, table):
        self.cursor.execute('SELECT last_value FROM "' + table + '_id_seq"')
        return self.cursor.fetchone()[0]

    def lock(self, table):
        self.cursor.execute('LOCK "%s" IN EXCLUSIVE MODE NOWAIT' % table)

    def has_constraint(self):
        return True

    def limit_clause(self, select, limit=None, offset=None):
        if limit is not None:
            select += ' LIMIT %d' % limit
        if offset is not None and offset != 0:
            select += ' OFFSET %d' % offset
        return select

    def has_returning(self):
        # RETURNING clause is available since PostgreSQL 8.2
        return self._database.get_version(self) >= (8, 2)

register_type(UNICODE)
if PYDATE:
    register_type(PYDATE)
if PYDATETIME:
    register_type(PYDATETIME)
if PYTIME:
    register_type(PYTIME)
register_adapter(float, lambda value: AsIs(repr(value)))
register_adapter(Decimal, lambda value: AsIs(str(value)))
