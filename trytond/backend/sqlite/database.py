# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import os
import threading
import time
from decimal import Decimal

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
from sql import Flavor, Table, Query, Expression, Literal
from sql.functions import (Function, Extract, Position, Substring,
    Overlay, CharLength, CurrentTimestamp, Trim)

from trytond.backend.database import DatabaseInterface, SQLType
from trytond.config import config

__all__ = ['Database', 'DatabaseIntegrityError', 'DatabaseOperationalError']
logger = logging.getLogger(__name__)


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
    if not _type:
        return date
    for format_ in [
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%H:%M:%S',
            ]:
        try:
            value = datetime.datetime.strptime(date, format_)
        except ValueError:
            continue
        else:
            break
    else:
        return None
    for attribute, replace in [
            ('microsecond', 0),
            ('second', 0),
            ('minute', 0),
            ('hour', 0),
            ('day', 1),
            ('month', 1)]:
        if _type.startswith(attribute):
            break
        value = value.replace(**{attribute: replace})
    return str(value)


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


class SQLiteCurrentTimestamp(Function):
    __slots__ = ()
    _function = 'NOW'  # More precise


class SQLiteTrim(Trim):

    def __str__(self):
        flavor = Flavor.get()
        param = flavor.param

        function = {
            'BOTH': 'TRIM',
            'LEADING': 'LTRIM',
            'TRAILING': 'RTRIM',
            }[self.position]

        def format(arg):
            if isinstance(arg, str):
                return param
            else:
                return str(arg)
        return function + '(%s, %s)' % (
            format(self.string), format(self.characters))


def sign(value):
    if value > 0:
        return 1
    elif value < 0:
        return -1
    else:
        return value


def greatest(*args):
    args = [a for a in args if a is not None]
    if args:
        return max(args)
    else:
        return None


def least(*args):
    args = [a for a in args if a is not None]
    if args:
        return min(args)
    else:
        return None


MAPPING = {
    Extract: SQLiteExtract,
    Position: SQLitePosition,
    Substring: SQLiteSubstring,
    Overlay: SQLiteOverlay,
    CharLength: SQLiteCharLength,
    CurrentTimestamp: SQLiteCurrentTimestamp,
    Trim: SQLiteTrim,
    }


class SQLiteCursor(sqlite.Cursor):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class SQLiteConnection(sqlite.Connection):

    def cursor(self):
        return super(SQLiteConnection, self).cursor(SQLiteCursor)


class Database(DatabaseInterface):

    _local = threading.local()
    _conn = None
    flavor = Flavor(
        paramstyle='qmark', function_mapping=MAPPING, null_ordering=False)
    IN_MAX = 200

    TYPES_MAPPING = {
        'DATETIME': SQLType('TIMESTAMP', 'TIMESTAMP'),
        'BIGINT': SQLType('INTEGER', 'INTEGER'),
        'BOOL': SQLType('BOOLEAN', 'BOOLEAN'),
        }

    def __new__(cls, name=':memory:'):
        if (name == ':memory:'
                and getattr(cls._local, 'memory_database', None)):
            return cls._local.memory_database
        return DatabaseInterface.__new__(cls, name=name)

    def __init__(self, name=':memory:'):
        super(Database, self).__init__(name=name)
        if name == ':memory:':
            Database._local.memory_database = self

    def connect(self):
        if self.name == ':memory:':
            path = ':memory:'
        else:
            db_filename = self.name + '.sqlite'
            path = os.path.join(config.get('database', 'path'), db_filename)
            if not os.path.isfile(path):
                raise IOError('Database "%s" doesn\'t exist!' % db_filename)
        if self._conn is not None:
            return self
        self._conn = sqlite.connect(path,
            detect_types=sqlite.PARSE_DECLTYPES | sqlite.PARSE_COLNAMES,
            factory=SQLiteConnection)
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
        self._conn.create_function('greatest', -1, greatest)
        self._conn.create_function('least', -1, least)
        if (hasattr(self._conn, 'set_trace_callback')
                and logger.isEnabledFor(logging.DEBUG)):
            self._conn.set_trace_callback(logger.debug)
        self._conn.execute('PRAGMA foreign_keys = ON')
        return self

    def get_connection(self, autocommit=False, readonly=False):
        if self._conn is None:
            self.connect()
        if autocommit:
            self._conn.isolation_level = None
        else:
            self._conn.isolation_level = 'IMMEDIATE'
        return self._conn

    def put_connection(self, connection=None, close=False):
        pass

    def close(self):
        if self.name == ':memory:':
            return
        if self._conn is None:
            return
        self._conn = None

    @classmethod
    def create(cls, connection, database_name):
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

    def drop(self, connection, database_name):
        if database_name == ':memory:':
            self._local.memory_database._conn = None
            return
        if os.sep in database_name:
            return
        os.remove(os.path.join(config.get('database', 'path'),
            database_name + '.sqlite'))

    def list(self, hostname=None):
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
                    database = Database(db_name).connect()
                except Exception:
                    continue
                if database.test(hostname=hostname):
                    res.append(db_name)
                database.close()
        return res

    def init(self):
        from trytond.modules import get_module_info
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
            with open(sql_file) as fp:
                for line in fp.read().split(';'):
                    if (len(line) > 0) and (not line.isspace()):
                        cursor.execute(line)

            ir_module = Table('ir_module')
            ir_module_dependency = Table('ir_module_dependency')
            for module in ('ir', 'res'):
                state = 'not activated'
                if module in ('ir', 'res'):
                    state = 'to activate'
                info = get_module_info(module)
                insert = ir_module.insert(
                    [ir_module.create_uid, ir_module.create_date,
                        ir_module.name, ir_module.state],
                    [[0, CurrentTimestamp(), module, state]])
                cursor.execute(*insert)
                cursor.execute('SELECT last_insert_rowid()')
                module_id, = cursor.fetchone()
                for dependency in info.get('depends', []):
                    insert = ir_module_dependency.insert(
                        [ir_module_dependency.create_uid,
                            ir_module_dependency.create_date,
                            ir_module_dependency.module,
                            ir_module_dependency.name,
                            ],
                        [[0, CurrentTimestamp(), module_id, dependency]])
                    cursor.execute(*insert)
            conn.commit()

    def test(self, hostname=None):
        tables = ['ir_model', 'ir_model_field', 'ir_ui_view', 'ir_ui_menu',
            'res_user', 'res_group', 'ir_module', 'ir_module_dependency',
            'ir_translation', 'ir_lang', 'ir_configuration']
        sqlite_master = Table('sqlite_master')
        select = sqlite_master.select(sqlite_master.name)
        select.where = sqlite_master.type == 'table'
        select.where &= sqlite_master.name.in_(tables)
        with self._conn as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(*select)
            except Exception:
                return False
            if len(cursor.fetchall()) != len(tables):
                return False
            if hostname:
                configuration = Table('ir_configuration')
                try:
                    cursor.execute(*configuration.select(
                            configuration.hostname))
                except Exception:
                    return False
                hostnames = {h for h, in cursor.fetchall() if h}
                if hostnames and hostname not in hostnames:
                    return False
        return True

    def lastid(self, cursor):
        # This call is not thread safe
        return cursor.lastrowid

    def lock(self, connection, table):
        pass

    def lock_id(self, id, timeout=None):
        return Literal(True)

    def has_constraint(self, constraint):
        return False

    def has_multirow_insert(self):
        return True

    def sql_type(self, type_):
        if type_ in self.TYPES_MAPPING:
            return self.TYPES_MAPPING[type_]
        if type_.startswith('VARCHAR'):
            return SQLType('VARCHAR', 'VARCHAR')
        return SQLType(type_, type_)

    def sql_format(self, type_, value):
        if type_ in ('INTEGER', 'BIGINT'):
            if (value is not None
                    and not isinstance(value, (Query, Expression))):
                value = int(value)
        return value

sqlite.register_converter('NUMERIC', lambda val: Decimal(val.decode('utf-8')))
sqlite.register_adapter(Decimal, lambda val: str(val).encode('utf-8'))


def adapt_datetime(val):
    return val.replace(tzinfo=None).isoformat(" ")
sqlite.register_adapter(datetime.datetime, adapt_datetime)
sqlite.register_adapter(datetime.time, lambda val: val.isoformat())
sqlite.register_converter('TIME',
    lambda val: datetime.time(*map(int, val.decode('utf-8').split(':'))))
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
