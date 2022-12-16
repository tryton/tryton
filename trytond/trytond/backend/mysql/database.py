#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import CONFIG
import MySQLdb
import MySQLdb.cursors
import MySQLdb.converters
from MySQLdb import IntegrityError as DatabaseIntegrityError
from MySQLdb import OperationalError as DatabaseOperationalError
import logging
import os
import re
import time
import tempfile

QUOTE_SEPARATION = re.compile(r"(.*?)('.*?')", re.DOTALL)
EXTRACT_EPOCH_PATTERN = re.compile(r'EXTRACT\s*\(\s*EPOCH\s+FROM',
        re.I)
CAST_VARCHAR_PATTERN = re.compile(r' AS VARCHAR\)', re.I)
CAST_INTEGER_PATTERN = re.compile(r' AS (INTEGER|BIGINT)\)', re.I)
SPLIT_PART_LEFT_PATTERN = re.compile(r'SPLIT_PART\((.*?),', re.I)
SPLIT_PART_RIGHT_PATTERN = re.compile(r'^,(\d)', re.I)


def _replace_split_part_right(mobj):
    pos = int(mobj.group(1))
    if pos not in (1, 2):
        raise Exception('SPLIT_PART is only partially implemented for MySQL')
    if pos == 2:
        return ', -1'
    return ', 1'


class Database(DatabaseInterface):

    _list_cache = None
    _list_cache_timestamp = None

    def connect(self):
        return self

    def cursor(self, autocommit=False, readonly=False):
        conv = MySQLdb.converters.conversions.copy()
        conv[float] = lambda value, _: repr(value)
        conv[MySQLdb.constants.FIELD_TYPE.TIME] = MySQLdb.times.Time_or_None
        args = {
            'db': self.database_name,
            'sql_mode': 'traditional,postgresql',
            'use_unicode': True,
            'charset': 'utf8',
            'conv': conv,
        }
        if CONFIG['db_host']:
            args['host'] = CONFIG['db_host']
        if CONFIG['db_port']:
            args['port'] = int(CONFIG['db_port'])
        if CONFIG['db_user']:
            args['user'] = CONFIG['db_user']
        if CONFIG['db_password']:
            args['passwd'] = CONFIG['db_password']
        conn = MySQLdb.connect(**args)
        return Cursor(conn, self.database_name)

    def close(self):
        return

    def create(self, cursor, database_name):
        cursor.execute('CREATE DATABASE `' + database_name + '` '
            'DEFAULT CHARACTER SET = \'utf8\'')
        Database._list_cache = None

    def drop(self, cursor, database_name):
        cursor.execute('DROP DATABASE `' + database_name + '`')
        Database._list_cache = None

    @staticmethod
    def dump(database_name):
        from trytond.tools import exec_pg_command_pipe

        cmd = ['mysqldump', '--no-create-db']
        if CONFIG['db_user']:
            cmd.append('--user=' + CONFIG['db_user'])
        if CONFIG['db_host']:
            cmd.append('--host=' + CONFIG['db_host'])
        if CONFIG['db_port']:
            cmd.append('--port=' + CONFIG['db_port'])
        if CONFIG['db_password']:
            cmd.append('--password=' + CONFIG['db_password'])
        cmd.append(database_name)

        pipe = exec_pg_command_pipe(*tuple(cmd))
        pipe.stdin.close()
        data = pipe.stdout.read()
        res = pipe.wait()
        if res:
            raise Exception('Couldn\'t dump database!')
        return data

    @staticmethod
    def restore(database_name, data):
        from trytond.tools import exec_pg_command_pipe

        database = Database().connect()
        cursor = database.cursor(autocommit=True)
        database.create(cursor, database_name)
        cursor.commit()
        cursor.close()

        cmd = ['mysql']
        if CONFIG['db_user']:
            cmd.append('--user=' + CONFIG['db_user'])
        if CONFIG['db_host']:
            cmd.append('--host=' + CONFIG['db_host'])
        if CONFIG['db_port']:
            cmd.append('--port=' + CONFIG['db_port'])
        if CONFIG['db_password']:
            cmd.append('--password=' + CONFIG['db_password'])
        cmd.append(database_name)

        fd, file_name = tempfile.mkstemp()
        with os.fdopen(fd, 'wb+') as fd:
            fd.write(data)

        cmd.append('<')
        cmd.append(file_name)

        args2 = tuple(cmd)

        pipe = exec_pg_command_pipe(*args2)
        pipe.stdin.close()
        res = pipe.wait()
        os.remove(file_name)
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
        timeout = int(CONFIG['session_timeout'])
        res = Database._list_cache
        if res and abs(Database._list_cache_timestamp - now) < timeout:
            return res
        cursor.execute('SHOW DATABASES')
        res = []
        for db_name, in cursor.fetchall():
            try:
                database = Database(db_name).connect()
            except Exception:
                continue
            cursor2 = database.cursor()
            if cursor2.test():
                res.append(db_name)
                cursor2.close(close=True)
            else:
                cursor2.close()
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
            cursor.execute('INSERT INTO ir_module_module '
                '(create_uid, create_date, name, state) '
                'VALUES (%s, now(), %s, %s)',
                (0, module, state))
            cursor.execute('SELECT LAST_INSERT_ID()')
            module_id, = cursor.fetchone()
            for dependency in info.get('depends', []):
                cursor.execute('INSERT INTO ir_module_module_dependency '
                    '(create_uid, create_date, module, name) '
                    'VALUES (%s, now(), %s, %s)',
                    (0, module_id, dependency))


class _Cursor(MySQLdb.cursors.Cursor):

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

    def fetchall(self):
        return list(super(_Cursor, self).fetchall())


class Cursor(CursorInterface):

    def __init__(self, conn, database_name):
        super(Cursor, self).__init__()
        self._conn = conn
        self.database_name = database_name
        self.dbname = self.database_name  # XXX to remove
        self.cursor = conn.cursor(_Cursor)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        buf = ""
        split_part_found = False
        for nquote, quote in QUOTE_SEPARATION.findall(sql + "''"):
            nquote = nquote.replace('ilike', 'like')
            nquote = re.sub(EXTRACT_EPOCH_PATTERN, r'UNIX_TIMESTAMP(',
                    nquote)
            nquote = re.sub(CAST_VARCHAR_PATTERN, r' AS CHAR)',
                    nquote)
            nquote = re.sub(CAST_INTEGER_PATTERN, r' AS SIGNED INTEGER)',
                    nquote)
            if split_part_found:
                nquote = re.sub(SPLIT_PART_RIGHT_PATTERN,
                    _replace_split_part_right, nquote)
                split_part_found = False
            nquote, split_part_found = re.subn(SPLIT_PART_LEFT_PATTERN,
                    r'SUBSTRING_INDEX(\1, ', nquote)

            buf += nquote + quote
        sql = buf[:-2]
        try:
            if params:
                res = self.cursor.execute(sql, params)
            else:
                res = self.cursor.execute(sql)
        except Exception, exception:
            logger = logging.getLogger('sql')
            logger.error('Wrong SQL: ' + sql + ' ' + str(params))
            if isinstance(exception, MySQLdb.Error):
                exception.args = exception.args[1:]
                raise exception
            raise
        return res

    def close(self, close=False):
        self.cursor.close()
        self.rollback()

    def commit(self):
        super(Cursor, self).commit()
        self._conn.commit()

    def rollback(self):
        super(Cursor, self).rollback()
        self._conn.rollback()

    def test(self):
        self.cursor.execute("SHOW TABLES")
        for table, in self.cursor.fetchall():
            if table in (
                    'ir_model',
                    'ir_model_field',
                    'ir_ui_view',
                    'ir_ui_menu',
                    'res_user',
                    'res_group',
                    'ir_module_module',
                    'ir_module_module_dependency',
                    'ir_translation',
                    'ir_lang',
                    ):
                return True
        return False

    def lastid(self):
        self.cursor.execute('SELECT LAST_INSERT_ID()')
        return self.cursor.fetchone()[0]

    def lock(self, table):
        # Lock of table doesn't work because MySQL require
        # that the session locks all tables that will be accessed
        # but 'FLUSH TABLES WITH READ LOCK' creates deadlock
        pass

    def has_constraint(self):
        return False

    def limit_clause(self, select, limit=None, offset=None):
        if offset and limit is None:
            limit = 18446744073709551610  # max bigint
        if limit is not None:
            select += ' LIMIT %d' % limit
        if offset is not None and offset != 0:
            select += ' OFFSET %d' % offset
        return select

    def update_auto_increment(self, table, value):
        self.cursor.execute('ALTER TABLE `%s` AUTO_INCREMENT = %%s' % table,
                value)
