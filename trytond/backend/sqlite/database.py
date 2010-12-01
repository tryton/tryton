#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import CONFIG
from trytond.session import Session
import logging
import os
import re
import mx.DateTime
from decimal import Decimal
import datetime

_FIX_ROWCOUNT = False
try:
    from pysqlite2 import dbapi2 as sqlite
    from pysqlite2.dbapi2 import IntegrityError as DatabaseIntegrityError
    from pysqlite2.dbapi2 import OperationalError as DatabaseOperationalError
    #pysqlite2 < 2.5 doesn't return correct rowcount
    _FIX_ROWCOUNT = sqlite.version_info < (2 , 5, 0)
except ImportError:
    import sqlite3 as sqlite
    from sqlite3 import IntegrityError as DatabaseIntegrityError
    from sqlite3 import OperationalError as DatabaseOperationalError
QUOTE_SEPARATION = re.compile(r"(.*?)('.*?')", re.DOTALL)
EXTRACT_PATTERN = re.compile(r'EXTRACT\s*\(\s*(\S*)\s+FROM', re.I)

def extract(lookup_type, date):
    if date is None:
        return None
    try:
        if len(date) == 10:
            year, month, day = map(int, date.split('-'))
            date = datetime.date(year, month, day)
        else:
            datepart, timepart = date.split(" ")
            year, month, day = map(int, datepart.split("-"))
            timepart_full = timepart.split(".")
            hours, minutes, seconds = map(int, timepart_full[0].split(":"))
            if len(timepart_full) == 2:
                microseconds = int(timepart_full[1])
            date = datetime.datetime(year, month, day, hours, minutes, seconds,
                    microseconds)
    except:
        return None
    if lookup_type.lower() == 'century':
        return date.year / 100 + (date.year % 100 and 1 or 0)
    elif lookup_type.lower() == 'decade':
        return date.year.year / 10
    elif lookup_type.lower() == 'dow':
        return (date.weekday() + 1) % 7
    elif lookup_type.lower() == 'doy':
        return date.day_of_year
    elif lookup_type.lower() == 'epoch':
        return date.ticks()
    elif lookup_type.lower() == 'microseconds':
        return int(a.second * 1000000)
    elif lookup_type.lower() == 'millennium':
        return date.year / 1000 + (date.year % 1000 and 1 or 0)
    elif lookup_type.lower() == 'milliseconds':
        return int(date.second * 1000)
    elif lookup_type.lower() == 'quarter':
        return date.month / 4 + 1
    elif lookup_type.lower() == 'week':
        return date.iso_week[1]
    return getattr(date, lookup_type)

def date_trunc(_type, date):
    if _type == 'second':
        return date
    try:
        date = mx.DateTime.strptime(date, '%Y-%m-%d %H:%M:%S')
    except:
        return None
    if _type == 'year':
        return "%i-01-01 00:00:00" % date.year
    elif _type == 'month':
        return "%i-%02i-01 00:00:00" % (date.year, date.month)
    elif _type == 'day':
        return "%i-%02i-%02i 00:00:00" % (date.year, date.month, date.day)

def split_part(text, delimiter, count):
    return (text.split(delimiter) + [''] * (count - 1))[count - 1]

def replace(text, pattern, replacement):
    return str(text).replace(pattern, replacement)


class Database(DatabaseInterface):

    _memory_database = None
    _conn = None

    def __new__(cls, database_name=':memory:'):
        if database_name == ':memory:' \
                and cls._memory_database:
            return cls._memory_database
        return DatabaseInterface.__new__(cls, database_name=database_name)

    def __init__(self, database_name=':memory:'):
        super(Database, self).__init__(database_name=database_name)
        if database_name == ':memory:':
            Database._memory_database = self

    def connect(self):
        if self.database_name == ':memory:':
            path = ':memory:'
        else:
            path = os.path.join(CONFIG['data_path'],
                    self.database_name + '.sqlite')
            if not os.path.isfile(path):
                raise Exception('Database doesn\'t exist!')
        if self._conn is not None:
            return self
        self._conn = sqlite.connect(path, detect_types=sqlite.PARSE_DECLTYPES)
        self._conn.create_function('extract', 2, extract)
        self._conn.create_function('date_trunc', 2, date_trunc)
        self._conn.create_function('split_part', 3, split_part)
        if sqlite.sqlite_version_info < (3, 3, 14):
            self._conn.create_function('replace', 3, replace)
        return self

    def cursor(self, autocommit=False):
        if self._conn is None:
            self.connect()
        if autocommit:
            self._conn.isolation_level = None
        else:
            self._conn.isolation_level = 'IMMEDIATE'
        return Cursor(self._conn, self.database_name)

    def close(self):
        if self.database_name == ':memory:':
            return
        if self._conn is None:
            return
        self._conn = None

    def create(self, cursor, database_name):
        if database_name == ':memory:':
            path = ':memory:'
        else:
            if os.sep in database_name:
                return
            path = os.path.join(CONFIG['data_path'],
                    database_name + '.sqlite')
        conn = sqlite.connect(path)
        cursor = conn.cursor()
        cursor.close()
        conn.close()

    def drop(self, cursor, database_name):
        if database_name == ':memory:':
            self._conn = None
            return
        if os.sep in database_name:
            return
        os.remove(os.path.join(CONFIG['data_path'],
            database_name + '.sqlite'))

    @staticmethod
    def dump(database_name):
        if database_name == ':memory:':
            raise Exception('Unable to dump memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(CONFIG['data_path'],
                database_name + '.sqlite')
        file_p = file(path, 'rb')
        data = file_p.read()
        file_p.close()
        return data

    @staticmethod
    def restore(database_name, data):
        if database_name == ':memory:':
            raise Exception('Unable to restore memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(CONFIG['data_path'],
                database_name + '.sqlite')
        if os.path.isfile(path):
            raise Exception('Database already exists!')
        file_p = file(path, 'wb')
        file_p.write(data)
        file_p.close()

    @staticmethod
    def list(cursor):
        res = []
        for file in os.listdir(CONFIG['data_path']) + [':memory:']:
            if file.endswith('.sqlite') or file == ':memory:':
                if file == ':memory:':
                    db_name = ':memory:'
                else:
                    db_name = file[:-7]
                try:
                    database = Database(db_name)
                except:
                    continue
                cursor2 = database.cursor()
                if cursor2.test():
                    res.append(db_name)
                cursor2.close()
        return res

    @staticmethod
    def init(cursor):
        from trytond.tools import safe_eval
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        for line in file(sql_file).read().split(';'):
            if (len(line)>0) and (not line.isspace()):
                cursor.execute(line)

        for i in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.join(os.path.dirname(__file__), '..', '..')
            tryton_file = os.path.join(root_path, i, '__tryton__.py')
            mod_path = os.path.join(root_path, i)
            info = safe_eval(file(tryton_file).read())
            active = info.get('active', False)
            if active:
                state = 'to install'
            else:
                state = 'uninstalled'
            cursor.execute('INSERT INTO ir_module_module ' \
                    '(create_uid, create_date, author, website, name, ' \
                    'shortdesc, description, state) ' \
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (0, datetime.datetime.now(), info.get('author', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), state))
            cursor.execute('SELECT last_insert_rowid()')
            module_id = cursor.fetchone()[0]
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(create_uid, create_date, module, name) ' \
                        'VALUES (%s, %s, %s, %s) ',
                        (0, datetime.datetime.now(), module_id, dependency))


class _Cursor(sqlite.Cursor):

    def __build_dict(self, row):
        res = {}
        for i in range(len(self.description)):
            res[self.description[i][0].strip('"')] = row[i]
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
    IN_MAX = 200

    def __init__(self, conn, database_name):
        super(Cursor, self).__init__()
        self._conn = conn
        self.database_name = database_name
        self.dbname = self.database_name #XXX to remove
        self.cursor = conn.cursor(_Cursor)

    def __getattr__(self, name):
        if _FIX_ROWCOUNT and name == 'rowcount':
            return -1
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        buf = ""
        for nq, q in QUOTE_SEPARATION.findall(sql+"''"):
            nq = nq.replace('?', '??')
            nq = nq.replace('%s', '?')
            nq = nq.replace('ilike', 'like')
            nq = re.sub(EXTRACT_PATTERN, r'EXTRACT("\1",', nq)
            buf += nq + q
        sql = buf[:-2]
        try:
            if params:
                res = self.cursor.execute(sql, [isinstance(x, str) and \
                        unicode(x, 'utf-8') or x for x in  params])
            else:
                res = self.cursor.execute(sql)
        except:
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
        try:
            self.cursor.execute("SELECT name " \
                    "FROM sqlite_master " \
                    "WHERE type = 'table' AND name in (" \
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
        except:
            return False
        return len(self.cursor.fetchall()) != 0

    def lastid(self):
        self.cursor.execute('SELECT last_insert_rowid()')
        return self.cursor.fetchone()[0]

    def has_lock(self):
        return False

    def has_constraint(self):
        return False

    def limit_clause(self, select, limit=None, offset=None):
        if limit is not None:
            select += ' LIMIT %d' % limit
        if offset is not None:
            if limit is None:
                select += ' LIMIT -1'
            select += ' OFFSET %d' % offset
        return select

sqlite.register_converter('NUMERIC', lambda val: Decimal(str(val)))
sqlite.register_adapter(Decimal, lambda val: float(val))
sqlite.register_adapter(Session, lambda val: int(val))
def adapt_datetime(val):
    return val.replace(tzinfo=None).isoformat(" ")
sqlite.register_adapter(datetime.datetime, adapt_datetime)
