#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import CONFIG
from trytond.session import Session
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import cursor
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import register_type, register_adapter
from psycopg2.extensions import UNICODE, AsIs
from psycopg2 import IntegrityError as DatabaseIntegrityError
from psycopg2 import OperationalError as DatabaseOperationalError
import time
import logging
import re
import os
if os.name == 'posix':
    import pwd

RE_FROM = re.compile('.* from "?([a-zA-Z_0-9]+)"?.*$')
RE_INTO = re.compile('.* into "?([a-zA-Z_0-9]+)"?.*$')


class Database(DatabaseInterface):

    _databases = {}
    _connpool = None

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
        host = CONFIG['db_host'] and "host=%s" % CONFIG['db_host'] or ''
        port = CONFIG['db_port'] and "port=%s" % CONFIG['db_port'] or ''
        name = "dbname=%s" % self.database_name
        user = CONFIG['db_user'] and "user=%s" % CONFIG['db_user'] or ''
        password = CONFIG['db_password'] \
                and "password=%s" % CONFIG['db_password'] or ''
        maxconn = int(CONFIG['db_maxconn']) or 64
        dsn = '%s %s %s %s %s' % (host, port, name, user, password)
        self._connpool = ThreadedConnectionPool(1, maxconn, dsn)
        return self

    def cursor(self, autocommit=False):
        if self._connpool is None:
            self.connect()
        conn = self._connpool.getconn()
        if autocommit:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        else:
            conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        return Cursor(self._connpool, conn, self.database_name)

    def close(self):
        if self._connpool is None:
            return
        self._connpool.closeall()
        self._connpool = None

    def create(self, cursor, database_name):
        cursor.execute('CREATE DATABASE "' + database_name + '" ' \
                'TEMPLATE template0 ENCODING \'unicode\'')

    def drop(self, cursor, database_name):
        cursor.execute('DROP DATABASE "' + database_name + '"')

    @staticmethod
    def dump(database_name):
        from trytond.tools import exec_pg_command_pipe
        if CONFIG['db_password']:
            raise Exception('Couldn\'t dump database with password!')
        cmd = ['pg_dump', '--format=c']
        if CONFIG['db_user']:
            cmd.append('--username=' + CONFIG['db_user'])
        if CONFIG['db_host']:
            cmd.append('--host=' + CONFIG['db_host'])
        if CONFIG['db_port']:
            cmd.append('--port=' + CONFIG['db_port'])
        cmd.append(database_name)

        stdin, stdout = exec_pg_command_pipe(*tuple(cmd))
        stdin.close()
        data = stdout.read()
        res = stdout.close()
        if res:
            raise Exception('Couldn\'t dump database!')
        return data

    @staticmethod
    def restore(database_name, data):
        from trytond.tools import exec_pg_command_pipe
        if CONFIG['db_password']:
            raise Exception('"Couldn\'t restore database with password!')

        database = Database().connect()
        cursor = database.cursor(autocommit=True)
        database.create(cursor, database_name)
        cursor.commit()
        cursor.close()

        cmd = ['pg_restore']
        if CONFIG['db_user']:
            cmd.append('--username=' + CONFIG['db_user'])
        if CONFIG['db_host']:
            cmd.append('--host=' + CONFIG['db_host'])
        if CONFIG['db_port']:
            cmd.append('--port=' + CONFIG['db_port'])
        cmd.append('--dbname=' + database_name)
        args2 = tuple(cmd)

        if os.name == "nt":
            tmpfile = (os.environ['TMP'] or 'C:\\') + os.tmpnam()
            file(tmpfile, 'wb').write(data)
            args2 = list(args2)
            args2.append(' ' + tmpfile)
            args2 = tuple(args2)

        stdin, stdout = exec_pg_command_pipe(*args2)
        if not os.name == "nt":
            stdin.write(data)
        stdin.close()
        res = stdout.close()
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
        return True

    @staticmethod
    def list(cursor):
        db_user = CONFIG['db_user']
        if not db_user and os.name == 'posix':
            db_user = pwd.getpwuid(os.getuid())[0]
        if not db_user:
            cursor.execute("SELECT usename " \
                    "FROM pg_user " \
                    "WHERE usesysid = (" \
                        "SELECT datdba " \
                        "FROM pg_database " \
                        "WHERE datname = %s)",
                        (CONFIG["db_name"],))
            res = cursor.fetchone()
            db_user = res and res[0]
        if db_user:
            cursor.execute("SELECT datname " \
                    "FROM pg_database " \
                    "WHERE datdba = (" \
                        "SELECT usesysid " \
                        "FROM pg_user " \
                        "WHERE usename=%s) " \
                        "AND datname not in " \
                            "('template0', 'template1', 'postgres') " \
                    "ORDER BY datname",
                            (db_user,))
        else:
            cursor.execute("SELECT datname " \
                    "FROM pg_database " \
                    "WHERE datname not in " \
                        "('template0', 'template1','postgres') " \
                    "ORDER BY datname")
        res = []
        for db_name, in cursor.fetchall():
            db_name = db_name.encode('utf-8')
            try:
                database = Database(db_name).connect()
            except:
                continue
            cursor2 = database.cursor()
            if cursor2.test():
                res.append(db_name)
                cursor2.close()
            else:
                cursor2.close()
                database.close()
        return res

    @staticmethod
    def init(cursor):
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        for line in file(sql_file).read().split(';'):
            if (len(line)>0) and (not line.isspace()):
                cursor.execute(line)

        for i in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.join(os.path.dirname(__file__), '..', '..')
            tryton_file = os.path.join(root_path, i, '__tryton__.py')
            mod_path = os.path.join(root_path, i)
            info = eval(file(tryton_file).read())
            active = info.get('active', False)
            if active:
                state = 'to install'
            else:
                state = 'uninstalled'
            cursor.execute('SELECT NEXTVAL(\'ir_module_module_id_seq\')')
            module_id = cursor.fetchone()[0]
            cursor.execute('INSERT INTO ir_module_module ' \
                    '(id, author, website, name, shortdesc, ' \
                    'description, state) ' \
                    'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (module_id, info.get('author', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), state))
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(module, name) VALUES (%s, %s)',
                        (module_id, dependency))


class _Cursor(cursor):

    def __build_dict(self, row):
        res = {}
        for i in range(len(self.description)):
            res[self.description[i][0]] = row[i]
        return res

    def dictfetchone(self):
        row = self.fetchone()
        if row:
            return self.__build_dict(row)
        else:
            return row

    def dictfetchmany(self, size):
        res = []
        rows = self.fetchmany(size)
        for row in rows:
            res.append(self.__build_dict(row))
        return res

    def dictfetchall(self):
        res = []
        rows = self.fetchall()
        for row in rows:
            res.append(self.__build_dict(row))
        return res


class Cursor(CursorInterface):

    def __init__(self, connpool, conn, database_name):
        self._connpool = connpool
        self._conn = conn
        self.database_name = database_name
        self.dbname = self.database_name #XX to remove
        self.cursor = conn.cursor(cursor_factory=_Cursor)
        self.commit()
        self.sql_from_log = {}
        self.sql_into_log = {}
        self.count = {
            'from': 0,
            'into': 0,
        }

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        if params is None:
            params = ()

        if self.sql_log:
            now = time.time()

        try:
            if params:
                res = self.cursor.execute(sql, params)
            else:
                res = self.cursor.execute(sql)
        except:
            logger = logging.getLogger('sql')
            logger.error('Wrong SQL: ' + (self.cursor.query or ''))
            raise
        if self.sql_log:
            res_from = RE_FROM.match(sql.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)][0] += 1
                self.sql_from_log[res_from.group(1)][1] += time.time() - now
                self.count['from'] += 1
            res_into = RE_INTO.match(sql.lower())
            if res_into:
                self.sql_into_log.setdefault(res_into.group(1), [0, 0])
                self.sql_into_log[res_into.group(1)][0] += 1
                self.sql_into_log[res_into.group(1)][1] += time.time() - now
                self.count['into'] += 1
        return res

    def _print_log(self, sql_type='from'):
        logger = logging.getLogger('sql')
        logger.info("SQL LOG %s:" % (sql_type,))
        if sql_type == 'from':
            logs = self.sql_from_log.items()
        else:
            logs = self.sql_into_log.items()
        logs.sort(lambda x, y: cmp(x[1][1], y[1][1]))
        amount = 0
        for log in logs:
            logger.info("table:%s:%f/%d" % (log[0], log[1][1], log[1][0]))
            amount += log[1][1]
        logger.info("SUM:%s/%d" % (amount, self.count[sql_type]))

    def close(self):
        if self.sql_log:
            self._print_log('from')
            self._print_log('into')
        self.cursor.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self.cursor
        #if id(self._conn) in self._connpool._rused:
        self.rollback()
        self._connpool.putconn(self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def test(self):
        self.cursor.execute("SELECT relname " \
                "FROM pg_class " \
                "WHERE relkind = 'r' AND relname in (" \
                "'ir_model', "
                "'ir_model_field', "
                "'ir_ui_view', "
                "'ir_ui_menu', "
                "'res_user', "
                "'res_group', "
                "'wkf', "
                "'wkf_activity', "
                "'wkf_transition', "
                "'wkf_instance', "
                "'wkf_workitem', "
                "'wkf_witm_trans', "
                "'ir_module_module', "
                "'ir_module_module_dependency', "
                "'ir_translation', "
                "'ir_lang'"
                ")")
        return len(self.cursor.fetchall()) != 0

register_type(UNICODE)
register_adapter(Session, AsIs)
