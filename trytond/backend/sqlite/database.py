# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.backend.database import DatabaseInterface, CursorInterface
from trytond.config import config
import os
from decimal import Decimal
import datetime
import time
import sys
import threading

_FIX_ROWCOUNT = False
try:
    from pysqlite2 import dbapi2 as sqlite
    from pysqlite2.dbapi2 import IntegrityError as DatabaseIntegrityError
    from pysqlite2.dbapi2 import OperationalError as DatabaseOperationalError
    # pysqlite2 < 2.5 doesn't return correct rowcount
    _FIX_ROWCOUNT = sqlite.version_info < (2, 5, 0)
except ImportError:
    import sqlite3 as sqlite
    from sqlite3 import IntegrityError as DatabaseIntegrityError
    from sqlite3 import OperationalError as DatabaseOperationalError
from sql import Flavor, Table
from sql.functions import (Function, Extract, Position, Now, Substring,
    Overlay, CharLength)

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError',
    'Cursor']


class SQLiteExtract(Function):
    __slots__ = ()
    _function = 'EXTRACT'

    @staticmethod
    def extract(lookup_type, date):
        if date is None:
            return None
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
            else:
                microseconds = 0
            date = datetime.datetime(year, month, day, hours, minutes, seconds,
                microseconds)
        if lookup_type.lower() == 'century':
            return date.year / 100 + (date.year % 100 and 1 or 0)
        elif lookup_type.lower() == 'decade':
            return date.year / 10
        elif lookup_type.lower() == 'dow':
            return (date.weekday() + 1) % 7
        elif lookup_type.lower() == 'doy':
            return date.timetuple().tm_yday
        elif lookup_type.lower() == 'epoch':
            return int(time.mktime(date.timetuple()))
        elif lookup_type.lower() == 'microseconds':
            return date.microsecond
        elif lookup_type.lower() == 'millennium':
            return date.year / 1000 + (date.year % 1000 and 1 or 0)
        elif lookup_type.lower() == 'milliseconds':
            return date.microsecond / 1000
        elif lookup_type.lower() == 'quarter':
            return date.month / 4 + 1
        elif lookup_type.lower() == 'week':
            return date.isocalendar()[1]
        return getattr(date, lookup_type.lower())


def date_trunc(_type, date):
    if _type == 'second':
        return date
    try:
        tm_tuple = time.strptime(date, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None
    if _type == 'year':
        return "%i-01-01 00:00:00" % tm_tuple.tm_year
    elif _type == 'month':
        return "%i-%02i-01 00:00:00" % (tm_tuple.tm_year, tm_tuple.tm_mon)
    elif _type == 'day':
        return "%i-%02i-%02i 00:00:00" % (tm_tuple.tm_year, tm_tuple.tm_mon,
                tm_tuple.tm_mday)


def split_part(text, delimiter, count):
    if text is None:
        return None
    return (text.split(delimiter) + [''] * (count - 1))[count - 1]


class SQLitePosition(Function):
    __slots__ = ()
    _function = 'POSITION'

    @staticmethod
    def position(substring, string):
        if string is None:
            return
        try:
            return string.index(substring) + 1
        except ValueError:
            return 0


def replace(text, pattern, replacement):
    return str(text).replace(pattern, replacement)


def now():
    return datetime.datetime.now().isoformat(' ')


class SQLiteSubstring(Function):
    __slots__ = ()
    _function = 'SUBSTR'


class SQLiteOverlay(Function):
    __slots__ = ()
    _function = 'OVERLAY'

    @staticmethod
    def overlay(string, placing_string, from_, for_=None):
        if for_ is None:
            for_ = len(placing_string)
        return string[:from_ - 1] + placing_string + string[from_ - 1 + for_:]


class SQLiteCharLength(Function):
    __slots__ = ()
    _function = 'LENGTH'


def sign(value):
    if value > 0:
        return 1
    elif value < 0:
        return -1
    else:
        return value


MAPPING = {
    Extract: SQLiteExtract,
    Position: SQLitePosition,
    Substring: SQLiteSubstring,
    Overlay: SQLiteOverlay,
    CharLength: SQLiteCharLength,
    }


class Database(DatabaseInterface):

    _local = threading.local()
    _conn = None
    flavor = Flavor(paramstyle='qmark', function_mapping=MAPPING)

    def __new__(cls, database_name=':memory:'):
        if (database_name == ':memory:'
                and getattr(cls._local, 'memory_database', None)):
            return cls._local.memory_database
        return DatabaseInterface.__new__(cls, database_name=database_name)

    def __init__(self, database_name=':memory:'):
        super(Database, self).__init__(database_name=database_name)
        if database_name == ':memory:':
            Database._local.memory_database = self

    def connect(self):
        if self.database_name == ':memory:':
            path = ':memory:'
        else:
            db_filename = self.database_name + '.sqlite'
            path = os.path.join(config.get('database', 'path'), db_filename)
            if not os.path.isfile(path):
                raise IOError('Database "%s" doesn\'t exist!' % db_filename)
        if self._conn is not None:
            return self
        self._conn = sqlite.connect(path,
            detect_types=sqlite.PARSE_DECLTYPES | sqlite.PARSE_COLNAMES)
        self._conn.create_function('extract', 2, SQLiteExtract.extract)
        self._conn.create_function('date_trunc', 2, date_trunc)
        self._conn.create_function('split_part', 3, split_part)
        self._conn.create_function('position', 2, SQLitePosition.position)
        self._conn.create_function('overlay', 3, SQLiteOverlay.overlay)
        self._conn.create_function('overlay', 4, SQLiteOverlay.overlay)
        if sqlite.sqlite_version_info < (3, 3, 14):
            self._conn.create_function('replace', 3, replace)
        self._conn.create_function('now', 0, now)
        self._conn.create_function('sign', 1, sign)
        self._conn.create_function('greatest', -1, max)
        self._conn.create_function('least', -1, min)
        self._conn.execute('PRAGMA foreign_keys = ON')
        return self

    def cursor(self, autocommit=False, readonly=False):
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

    @staticmethod
    def create(cursor, database_name):
        if database_name == ':memory:':
            path = ':memory:'
        else:
            if os.sep in database_name:
                return
            path = os.path.join(config.get('database', 'path'),
                    database_name + '.sqlite')
        with sqlite.connect(path) as conn:
            cursor = conn.cursor()
            cursor.close()

    @classmethod
    def drop(cls, cursor, database_name):
        if database_name == ':memory:':
            cls._local.memory_database._conn = None
            return
        if os.sep in database_name:
            return
        os.remove(os.path.join(config.get('database', 'path'),
            database_name + '.sqlite'))

    @staticmethod
    def dump(database_name):
        if database_name == ':memory:':
            raise Exception('Unable to dump memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(config.get('database', 'path'),
                database_name + '.sqlite')
        with open(path, 'rb') as file_p:
            data = file_p.read()
        return data

    @staticmethod
    def restore(database_name, data):
        if database_name == ':memory:':
            raise Exception('Unable to restore memory database!')
        if os.sep in database_name:
            raise Exception('Wrong database name!')
        path = os.path.join(config.get('database', 'path'),
                database_name + '.sqlite')
        if os.path.isfile(path):
            raise Exception('Database already exists!')
        with open(path, 'wb') as file_p:
            file_p.write(data)

    @staticmethod
    def list(cursor):
        res = []
        listdir = [':memory:']
        try:
            listdir += os.listdir(config.get('database', 'path'))
        except OSError:
            pass
        for db_file in listdir:
            if db_file.endswith('.sqlite') or db_file == ':memory:':
                if db_file == ':memory:':
                    db_name = ':memory:'
                else:
                    db_name = db_file[:-7]
                try:
                    database = Database(db_name)
                except Exception:
                    continue
                cursor2 = database.cursor()
                if cursor2.test():
                    res.append(db_name)
                cursor2.close()
        return res

    @staticmethod
    def init(cursor):
        from trytond.modules import get_module_info
        sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
        with open(sql_file) as fp:
            for line in fp.read().split(';'):
                if (len(line) > 0) and (not line.isspace()):
                    cursor.execute(line)

        ir_module = Table('ir_module_module')
        ir_module_dependency = Table('ir_module_module_dependency')
        for module in ('ir', 'res', 'webdav'):
            state = 'uninstalled'
            if module in ('ir', 'res'):
                state = 'to install'
            info = get_module_info(module)
            insert = ir_module.insert(
                [ir_module.create_uid, ir_module.create_date, ir_module.name,
                    ir_module.state],
                [[0, Now(), module, state]])
            cursor.execute(*insert)
            cursor.execute('SELECT last_insert_rowid()')
            module_id, = cursor.fetchone()
            for dependency in info.get('depends', []):
                insert = ir_module_dependency.insert(
                    [ir_module_dependency.create_uid,
                        ir_module_dependency.create_date,
                        ir_module_dependency.module, ir_module_dependency.name
                        ],
                    [[0, Now(), module_id, dependency]])
                cursor.execute(*insert)


class _Cursor(sqlite.Cursor):

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
    IN_MAX = 200

    def __init__(self, conn, database_name):
        super(Cursor, self).__init__()
        self._conn = conn
        self.database_name = database_name
        self.dbname = self.database_name  # XXX to remove
        self.cursor = conn.cursor(_Cursor)

    def __getattr__(self, name):
        if _FIX_ROWCOUNT and name == 'rowcount':
            return -1
        return getattr(self.cursor, name)

    def execute(self, sql, params=None):
        if params:
            return self.cursor.execute(sql, params)
        else:
            return self.cursor.execute(sql)

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
        sqlite_master = Table('sqlite_master')
        select = sqlite_master.select(sqlite_master.name)
        select.where = sqlite_master.type == 'table'
        select.where &= sqlite_master.name.in_([
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
                ])
        try:
            self.cursor.execute(*select)
        except Exception:
            return False
        return len(self.cursor.fetchall()) != 0

    def lastid(self):
        self.cursor.execute('SELECT last_insert_rowid()')
        return self.cursor.fetchone()[0]

    def lock(self, table):
        pass

    def has_constraint(self):
        return False

sqlite.register_converter('NUMERIC', lambda val: Decimal(val.decode('utf-8')))
if sys.version_info[0] == 2:
    sqlite.register_adapter(Decimal, lambda val: buffer(str(val)))
    sqlite.register_adapter(bytearray, lambda val: buffer(val))
else:
    sqlite.register_adapter(Decimal, lambda val: str(val).encode('utf-8'))


def adapt_datetime(val):
    return val.replace(tzinfo=None).isoformat(" ")
sqlite.register_adapter(datetime.datetime, adapt_datetime)
sqlite.register_adapter(datetime.time, lambda val: val.isoformat())
sqlite.register_converter('TIME', lambda val: datetime.time(*map(int,
            val.decode('utf-8').split(':'))))
sqlite.register_adapter(datetime.timedelta, lambda val: val.total_seconds())


def convert_interval(value):
    value = float(value)
    # It is not allowed to instatiate timedelta with the min/max total seconds
    if value >= _interval_max:
        return datetime.timedelta.max
    elif value <= _interval_min:
        return datetime.timedelta.min
    return datetime.timedelta(seconds=value)
_interval_max = datetime.timedelta.max.total_seconds()
_interval_min = datetime.timedelta.min.total_seconds()
sqlite.register_converter('INTERVAL', convert_interval)
