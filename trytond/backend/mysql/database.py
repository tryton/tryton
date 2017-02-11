# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.backend.database import DatabaseInterface
from trytond.config import config, parse_uri
import MySQLdb
import MySQLdb.cursors
import MySQLdb.converters
from MySQLdb import IntegrityError as DatabaseIntegrityError
from MySQLdb import OperationalError as DatabaseOperationalError
import os
import time
import urllib

from sql import Flavor, Expression
from sql.functions import Extract, Overlay, CharLength

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError']


class MySQLExtract(Extract):

    def is_epoch(self):
        return self.args[0].upper() == 'EPOCH'

    def __str__(self):
        if self.is_epoch():
            return 'UNIX_TIMESTAMP(%s)' % self._format(self.args[1])
        return super(MySQLExtract, self).__str__()

    @property
    def params(self):
        if self.is_epoch():
            arg = self.args[1]
            if isinstance(arg, Expression):
                return arg.params
            else:
                return (arg,)
        return super(MySQLExtract, self).params


class MySQLOverlay(Overlay):

    @property
    def mysql_args(self):
        if len(self.args) == 3:
            string, placing, from_ = self.args
            for_ = CharLength(placing)
        else:
            string, placing, from_, for_ = self.args
        return (string, from_, placing, string, from_, for_)

    def __str__(self):
        return ('CONCAT(SUBSTRING(%s FROM 1 FOR %s), %s, '
            'SUBSTRING(%s FROM %s + 1 + %s))'
            % tuple(map(self._format, self.mysql_args)))

    @property
    def params(self):
        p = ()
        for arg in self.mysql_args:
            if isinstance(arg, Expression):
                p += arg.params
            else:
                p += (arg,)
        return p


MAPPING = {
    Extract: MySQLExtract,
    Overlay: MySQLOverlay,
    }


class Database(DatabaseInterface):

    _list_cache = None
    _list_cache_timestamp = None
    flavor = Flavor(max_limit=18446744073709551610, function_mapping=MAPPING)

    def connect(self):
        return self

    def get_connection(self, autocommit=False, readonly=False):
        conv = MySQLdb.converters.conversions.copy()
        conv[float] = lambda value, _: repr(value)
        conv[MySQLdb.constants.FIELD_TYPE.TIME] = MySQLdb.times.Time_or_None
        args = {
            'db': self.name,
            'sql_mode': 'traditional,postgresql',
            'use_unicode': True,
            'charset': 'utf8',
            'conv': conv,
        }
        uri = parse_uri(config.get('database', 'uri'))
        assert uri.scheme == 'mysql'
        if uri.hostname:
            args['host'] = uri.hostname
        if uri.port:
            args['port'] = uri.port
        if uri.username:
            args['user'] = uri.username
        if uri.password:
            args['passwd'] = urllib.unquote_plus(uri.password)
        conn = MySQLdb.connect(**args)
        cursor = conn.cursor()
        cursor.execute('SET time_zone = "+00:00"')
        return conn

    def put_connection(self, connection, close=False):
        connection.close()

    def close(self):
        return

    @classmethod
    def create(cls, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('CREATE DATABASE `' + database_name + '` '
            'DEFAULT CHARACTER SET = \'utf8\'')
        cls._list_cache = None

    @classmethod
    def drop(cls, connection, database_name):
        cursor = connection.cursor()
        cursor.execute('DROP DATABASE `' + database_name + '`')
        cls._list_cache = None

    def list(self):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = Database._list_cache
        if res and abs(Database._list_cache_timestamp - now) < timeout:
            return res
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SHOW DATABASES')
        res = []
        for db_name, in cursor.fetchall():
            try:
                database = Database(db_name).connect()
            except Exception:
                continue
            if database.test():
                res.append(db_name)
            database.close()
        self.put_connection(conn)
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
            state = 'not activated'
            if module in ('ir', 'res'):
                state = 'to activate'
            info = get_module_info(module)
            cursor.execute('INSERT INTO ir_module '
                '(create_uid, create_date, name, state) '
                'VALUES (%s, now(), %s, %s)',
                (0, module, state))
            cursor.execute('SELECT LAST_INSERT_ID()')
            module_id, = cursor.fetchone()
            for dependency in info.get('depends', []):
                cursor.execute('INSERT INTO ir_module_dependency '
                    '(create_uid, create_date, module, name) '
                    'VALUES (%s, now(), %s, %s)',
                    (0, module_id, dependency))

        connection.commit()
        self.put_connection(connection)

    def test(self):
        is_tryton_database = False
        connection = self.get_connection()
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        for table, in cursor.fetchall():
            if table in (
                    'ir_model',
                    'ir_model_field',
                    'ir_ui_view',
                    'ir_ui_menu',
                    'res_user',
                    'res_group',
                    'ir_module',
                    'ir_module_dependency',
                    'ir_translation',
                    'ir_lang',
                    ):
                is_tryton_database = True
                break
        self.put_connection(connection)
        return is_tryton_database

    def lastid(self, cursor):
        # This call is not thread safe
        cursor.execute('SELECT LAST_INSERT_ID()')
        return cursor.fetchone()[0]

    def lock(self, connection, table):
        # Lock of table doesn't work because MySQL require
        # that the session locks all tables that will be accessed
        # but 'FLUSH TABLES WITH READ LOCK' creates deadlock
        pass

    def has_constraint(self):
        return False

    def has_multirow_insert(self):
        return True

    def update_auto_increment(self, connection, table, value):
        cursor = connection.cursor()
        cursor.execute('ALTER TABLE `%s` AUTO_INCREMENT = %%s' % table,
                (value,))
