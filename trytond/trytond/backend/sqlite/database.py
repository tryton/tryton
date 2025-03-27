# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import logging
import math
import os
import random
import sqlite3 as sqlite
import threading
import time
import urllib.parse
import warnings
from decimal import Decimal
from sqlite3 import DatabaseError
from sqlite3 import IntegrityError as DatabaseIntegrityError
from sqlite3 import OperationalError as DatabaseOperationalError
from weakref import WeakKeyDictionary

from sql import Expression, Flavor, Literal, Null, Query, Table
from sql.aggregate import Count
from sql.conditionals import NullIf
from sql.functions import (
    CharLength, CurrentTimestamp, Extract, Function, Overlay, Position,
    Substring, Trim)
from sql.operators import Equal

from trytond import __series__
from trytond.backend.database import DatabaseInterface, SQLType
from trytond.config import config, parse_uri
from trytond.tools import safe_join
from trytond.transaction import Transaction

__all__ = [
    'Database',
    'DatabaseIntegrityError', 'DatabaseDataError', 'DatabaseOperationalError',
    'DatabaseTimeoutError']
logger = logging.getLogger(__name__)

_default_name = config.get('database', 'default_name', default=':memory:')


class DatabaseDataError(DatabaseError):
    pass


class DatabaseTimeoutError(Exception):
    pass


class SQLiteExtract(Function):
    __slots__ = ()
    _function = 'EXTRACT'

    @staticmethod
    def extract(lookup_type, source):
        if source is None:
            return None

        if isinstance(source, (int, float)):  # interval
            source = dt.timedelta(seconds=source)
        else:
            for fromisoformat in [
                    dt.date.fromisoformat,
                    dt.time.fromisoformat,
                    dt.datetime.fromisoformat,
                    ]:
                try:
                    source = fromisoformat(source)
                except ValueError:
                    continue
                break
            else:
                raise ValueError
        lookup_type = lookup_type.lower()
        if lookup_type == 'century':
            if isinstance(source, dt.date):
                return source.year // 100 + (source.year % 100 and 1 or 0)
            elif isinstance(source, dt.timedelta):
                return 0
        elif lookup_type == 'day':
            if isinstance(source, dt.date):
                return source.day
            elif isinstance(source, dt.timedelta):
                return source.days
        elif lookup_type == 'decade':
            if isinstance(source, dt.date):
                return source.year // 10
        elif lookup_type == 'dow':
            if isinstance(source, dt.date):
                return (source.weekday() + 1) % 7
        elif lookup_type == 'doy':
            if isinstance(source, dt.date):
                return source.timetuple().tm_yday
        elif lookup_type == 'epoch':
            if isinstance(source, dt.datetime):
                return source.timestamp()
            elif isinstance(source, dt.date):
                return int(dt.datetime.combine(source, dt.time()).timestamp())
            elif isinstance(source, dt.timedelta):
                return (
                    source.days * 24 * 60 * 60
                    + source.seconds
                    + source.microseconds / 1_000_000)
        elif lookup_type == 'hour':
            if isinstance(source, (dt.datetime, dt.time)):
                return source.hour
            elif isinstance(source, dt.timedelta):
                return source.seconds // 60 // 60
        elif lookup_type == 'isodow':
            if isinstance(source, dt.date):
                return source.isoweekday()
        elif lookup_type == 'isoyear':
            if isinstance(source, dt.date):
                return source.isocalendar()[0]
        elif lookup_type == 'microseconds':
            if isinstance(source, (dt.datetime, dt.time)):
                return source.second * 1_000_000 + source.microsecond
            elif isinstance(source, dt.timedelta):
                return (source.seconds % 60) * 1_000_000 + source.microseconds
        elif lookup_type == 'millennium':
            if isinstance(source, dt.date):
                return source.year // 1000 + (source.year % 1000 and 1 or 0)
            elif isinstance(source, dt.timedelta):
                return 0
        elif lookup_type == 'milliseconds':
            if isinstance(source, (dt.datetime, dt.time)):
                return source.second * 1_000 + source.microsecond / 1_000
            elif isinstance(source, dt.timedelta):
                return (
                    (source.seconds % 60) * 1_000
                    + source.microseconds / 1_000)
        elif lookup_type == 'minute':
            if isinstance(source, (dt.datetime, dt.time)):
                return source.minute
            elif isinstance(source, dt.timedelta):
                return source.seconds // 60
        elif lookup_type == 'month':
            if isinstance(source, dt.date):
                return source.month
            elif isinstance(source, dt.timedelta):
                return 0
        elif lookup_type == 'quarter':
            if isinstance(source, dt.date):
                return source.month // 4 + 1
            elif isinstance(source, dt.timedelta):
                return 1
        elif lookup_type == 'second':
            if isinstance(source, (dt.datetime, dt.time)):
                return source.second + source.microsecond / 1_000_000
            elif isinstance(source, dt.timedelta):
                return (source.seconds % 60) + source.microseconds / 1_000_000
        elif lookup_type == 'week':
            if isinstance(source, dt.date):
                return source.isocalendar()[1]
        elif lookup_type == 'year':
            if isinstance(source, dt.date):
                return source.year
            elif isinstance(source, dt.timedelta):
                return 0
        raise ValueError


def date_trunc(field, source):
    if field is None or source is None:
        return None
    if isinstance(source, (int, float)):  # interval
        return _date_trunc_interval(field, source)
    for fromisoformat in [
            dt.date.fromisoformat,
            dt.time.fromisoformat,
            dt.datetime.fromisoformat,
            ]:
        try:
            value = fromisoformat(source)
        except ValueError:
            continue
        else:
            break
    else:
        return None
    field = field.lower()
    for attribute, replace in [
            ('microsecond', 0),
            ('second', 0),
            ('minute', 0),
            ('hour', 0),
            ('day', 1),
            ('month', 1),
            ]:
        if field.startswith(attribute):
            break
        if hasattr(value, attribute):
            value = value.replace(**{attribute: replace})
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        value = dt.datetime.combine(value, dt.time())
    elif isinstance(value, dt.time):
        value = (
            dt.datetime.combine(dt.date.min, value)
            - dt.datetime.min)
    if isinstance(value, dt.datetime):
        return adapt_datetime(value)
    else:
        return adapt_timedelta(value)


def _date_trunc_interval(field, source):
    value = dt.timedelta(seconds=source)
    field = field.lower()
    for attribute, delta in [
            ('microseconds', value.microseconds),
            ('seconds', value.seconds % 60),
            ('minutes', (value.seconds // 60) % 60),
            ('hours', (value.seconds // (60 * 60)) % 24),
            ('days', value.days),
            ]:
        if field.startswith(attribute[:-1]):
            break
        value -= dt.timedelta(**{attribute: delta})
    return adapt_timedelta(value)


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
    transaction = Transaction()
    return _nows.setdefault(transaction, {}).setdefault(
        transaction.started_at, dt.datetime.now().isoformat(' '))


_nows = WeakKeyDictionary()


def to_char(value, format):
    for fromisoformat in [
            dt.date.fromisoformat,
            dt.time.fromisoformat,
            dt.datetime.fromisoformat,
            ]:
        try:
            value = fromisoformat(value)
        except ValueError:
            continue
        break
    if isinstance(value, dt.date):
        # Convert SQL pattern into compatible Python
        return value.strftime(format
            .replace('%', '%%')
            .replace('HH12', '%I')
            .replace('HH24', '%H')
            .replace('HH', '%I')
            .replace('MI', '%M')
            .replace('SS', '%S')
            .replace('US', '%f')
            .replace('AM', '%p')
            .replace('A.M.', '%p')
            .replace('PM', '%p')
            .replace('P.M.', '%p')
            .replace('am', '%p')
            .replace('a.m.', '%p')
            .replace('pm', '%p')
            .replace('p.m.', '%p')
            .replace('YYYY', '%Y')
            .replace('YY', '%y')
            .replace('Month', '%B')
            .replace('Mon', '%b')
            .replace('MM', '%m')
            .replace('Day', '%A')
            .replace('Dy', '%a')
            .replace('DDD', '%j')
            .replace('DD', '%d')
            .replace('D', '%w')
            .replace('TZ', '%Z')
            )
    elif isinstance(value, dt.timedelta):
        raise NotImplementedError
    else:
        raise NotImplementedError


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

    @property
    def params(self):
        if isinstance(self.string, str):
            params = [self.string]
        else:
            params = list(self.string.params)
        params.append(self.characters)
        return params


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


def bool_and(*args):
    return all(args)


def bool_or(*args):
    return any(args)


def cbrt(value):
    return math.pow(value, 1 / 3)


def div(a, b):
    return a // b


def trunc(value, digits):
    return math.trunc(value * 10 ** digits) / 10 ** digits


MAPPING = {
    Extract: SQLiteExtract,
    Position: SQLitePosition,
    Substring: SQLiteSubstring,
    Overlay: SQLiteOverlay,
    CharLength: SQLiteCharLength,
    CurrentTimestamp: SQLiteCurrentTimestamp,
    Trim: SQLiteTrim,
    }


class JSONExtract(Function):
    __slots__ = ()
    _function = 'JSON_EXTRACT'


class JSONQuote(Function):
    __slots__ = ()
    _function = 'JSON_QUOTE'


class SQLiteCursor(sqlite.Cursor):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class SQLiteConnection(sqlite.Connection):

    def cursor(self):
        return super().cursor(SQLiteCursor)


class Database(DatabaseInterface):

    _local = threading.local()
    _conn = None
    _list_cache = {}
    _list_cache_timestamp = {}
    flavor = Flavor(
        paramstyle='qmark', function_mapping=MAPPING, null_ordering=False,
        max_limit=-1)
    IN_MAX = 200

    TYPES_MAPPING = {
        'BIGINT': SQLType('INTEGER', 'INTEGER'),
        'BOOL': SQLType('BOOLEAN', 'BOOLEAN'),
        'DATETIME': SQLType('TIMESTAMP', 'TIMESTAMP'),
        'FULLTEXT': SQLType('TEXT', 'TEXT'),
        'JSON': SQLType('TEXT', 'TEXT'),
        }

    def __new__(cls, name=_default_name):
        if (name == ':memory:'
                and getattr(cls._local, 'memory_database', None)):
            return cls._local.memory_database
        return DatabaseInterface.__new__(cls, name=name)

    def __init__(self, name=_default_name):
        super().__init__(name=name)
        if name == ':memory:':
            Database._local.memory_database = self

    def connect(self):
        if self._conn is not None:
            return self
        self._conn = sqlite.connect(
            self._make_uri(), uri=True,
            detect_types=sqlite.PARSE_DECLTYPES | sqlite.PARSE_COLNAMES,
            factory=SQLiteConnection)
        self._conn.create_function('extract', 2, SQLiteExtract.extract)
        self._conn.create_function('date_trunc', 2, date_trunc)
        self._conn.create_function('split_part', 3, split_part)
        self._conn.create_function('to_char', 2, to_char)
        if sqlite.sqlite_version_info < (3, 3, 14):
            self._conn.create_function('replace', 3, replace)
        self._conn.create_function('now', 0, now)
        self._conn.create_function('greatest', -1, greatest)
        self._conn.create_function('least', -1, least)
        self._conn.create_function('bool_and', -1, bool_and)
        self._conn.create_function('bool_or', -1, bool_or)

        # Mathematical functions
        self._conn.create_function('cbrt', 1, cbrt)
        self._conn.create_function('ceil', 1, math.ceil)
        self._conn.create_function('degrees', 1, math.degrees)
        self._conn.create_function('div', 2, div)
        self._conn.create_function('exp', 1, math.exp)
        self._conn.create_function('floor', 1, math.floor)
        self._conn.create_function('ln', 1, math.log)
        self._conn.create_function('log', 1, math.log10)
        self._conn.create_function('mod', 2, math.fmod)
        self._conn.create_function('pi', 0, lambda: math.pi)
        self._conn.create_function('power', 2, math.pow)
        self._conn.create_function('radians', 1, math.radians)
        self._conn.create_function('sign', 1, sign)
        self._conn.create_function('sqrt', 1, math.sqrt)
        self._conn.create_function('trunc', 1, math.trunc)
        self._conn.create_function('trunc', 2, trunc)

        # Trigonomentric functions
        self._conn.create_function('acos', 1, math.acos)
        self._conn.create_function('asin', 1, math.asin)
        self._conn.create_function('atan', 1, math.atan)
        self._conn.create_function('atan2', 2, math.atan2)
        self._conn.create_function('cos', 1, math.cos)
        self._conn.create_function(
            'cot', 1, lambda x: 1 / math.tan(x) if x else math.inf)
        self._conn.create_function('sin', 1, math.sin)
        self._conn.create_function('tan', 1, math.tan)

        # Random functions
        self._conn.create_function('random', 0, random.random)
        self._conn.create_function('setseed', 1, random.seed)

        # String functions
        self._conn.create_function('overlay', 3, SQLiteOverlay.overlay)
        self._conn.create_function('overlay', 4, SQLiteOverlay.overlay)
        self._conn.create_function('position', 2, SQLitePosition.position)

        if (hasattr(self._conn, 'set_trace_callback')
                and logger.isEnabledFor(logging.DEBUG)):
            self._conn.set_trace_callback(logger.debug)
        self._conn.execute('PRAGMA foreign_keys = ON')
        self._conn.execute('PRAGMA journal_mode = WAL')
        self._conn.execute('PRAGMA synchronous = NORMAL')
        try:
            self._conn.execute('PRAGMA optimize')
        except DatabaseOperationalError:
            # database may be locked
            pass
        return self

    def _make_uri(self):
        uri = config.get('database', 'uri')
        base_uri = parse_uri(uri)
        if base_uri.path and base_uri.path != '/':
            warnings.warn("The path specified in the URI will be overridden")

        if self.name == ':memory:':
            query_string = urllib.parse.parse_qs(base_uri.query)
            query_string['mode'] = 'memory'
            query = urllib.parse.urlencode(query_string, doseq=True)
            db_uri = base_uri._replace(netloc='', path='/', query=query)
        else:
            db_path = safe_join(
                config.get('database', 'path'), self.name + '.sqlite')
            if not os.path.isfile(db_path):
                raise IOError("Database '%s' doesn't exist!" % db_path)
            db_uri = base_uri._replace(path=db_path)

        # Use unparse before replacing sqlite with file because SQLite accepts
        # a relative path URI like file:db/test.sqlite which doesn't conform to
        # RFC8089 which urllib follows and enforces when the scheme is 'file'
        db_uri = urllib.parse.urlunparse(db_uri)
        return db_uri.replace('sqlite', 'file', 1)

    def get_connection(
            self, autocommit=False, readonly=False, statement_timeout=None):
        if self._conn is None:
            self.connect()
        if autocommit:
            self._conn.isolation_level = None
        else:
            self._conn.isolation_level = 'IMMEDIATE'
        return self._conn

    def put_connection(self, connection=None, close=False):
        assert connection == self._conn or self._conn is None
        if self.name == ':memory:':
            if (self._local.memory_database._conn is None
                    and connection and close):
                connection.close()
                self._conn = None
        elif close:
            connection.close()
            self._conn = None

    def close(self):
        if self.name == ':memory:':
            if (self._local.memory_database._conn is None
                    and self._conn):
                self._conn.close()
                self._conn = None
        elif self._conn:
            self._conn.close()
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
        cls._list_cache.clear()

    @classmethod
    def drop(cls, connection, database_name):
        if os.sep in database_name:
            return
        if database_name == ':memory:':
            cls._local.memory_database._conn = None
        else:
            file = os.path.join(
                config.get('database', 'path'), database_name + '.sqlite')
            os.remove(file)
            for suffix in ['-shm', '-wal']:
                try:
                    os.remove(file + suffix)
                except FileNotFoundError:
                    pass
        cls._list_cache.clear()

    def list(self, hostname=None):
        now = time.time()
        timeout = config.getint('session', 'timeout')
        res = self.__class__._list_cache.get(hostname)
        timestamp = self.__class__._list_cache_timestamp.get(hostname, now)
        if res and abs(timestamp - now) < timeout:
            return res

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
                    logger.debug(
                        'Test failed for "%s"', db_name, exc_info=True)
                    continue
                if database.test(hostname=hostname, series=True):
                    res.append(db_name)
                database.close()

        self.__class__._list_cache[hostname] = res
        self.__class__._list_cache_timestamp[hostname] = now
        return res

    def init(self):
        from trytond.modules import get_module_info
        Flavor.set(self.flavor)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
            with open(sql_file) as fp:
                for line in fp.read().split(';'):
                    if (len(line) > 0) and (not line.isspace()):
                        cursor.execute(line)

            ir_module = Table('ir_module')
            ir_module_dependency = Table('ir_module_dependency')
            for module in ['ir', 'res']:
                info = get_module_info(module)
                insert = ir_module.insert(
                    [ir_module.create_uid, ir_module.create_date,
                        ir_module.name, ir_module.state],
                    [[0, CurrentTimestamp(), module, 'to activate']])
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

    def test(self, hostname=None, series=False):
        with self._conn as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'SELECT name FROM sqlite_master '
                    'WHERE type = ? AND name = ?',
                    ('table', 'ir_configuration'))
            except Exception:
                return False
            if not cursor.fetchall():
                return False
            if series:
                try:
                    cursor.execute('SELECT series FROM ir_configuration')
                except Exception:
                    return False
                config_series = {s for s, in cursor if s}
                if config_series and __series__ not in config_series:
                    return False
            if hostname:
                try:
                    cursor.execute('SELECT hostname FROM ir_configuration')
                except Exception:
                    return False
                hostnames = {h for h, in cursor if h}
                if hostnames and hostname not in hostnames:
                    return False
        return True

    def lastid(self, cursor):
        # This call is not thread safe
        return cursor.lastrowid

    def estimated_count(self, connection, table):
        cursor = connection.cursor()
        cursor.execute(*table.select(Count(Literal('*'))))
        return cursor.fetchone()[0]

    @classmethod
    def lock(cls, connection, table):
        pass

    @classmethod
    def lock_records(cls, connection, table, ids):
        pass

    def lock_id(self, id, timeout=None):
        return Literal(True)

    def has_constraint(self, constraint):
        from trytond.model.modelsql import Exclude, Unique
        return (
            not constraint.params
            and (isinstance(constraint, Unique)
                or (isinstance(constraint, Exclude)
                    and set(constraint.operators) == {Equal})))

    def has_multirow_insert(self):
        return True

    def has_insert_on_conflict(self):
        return sqlite.sqlite_version_info >= (3, 35, 0)

    def has_window_functions(self):
        return sqlite.sqlite_version_info >= (3, 25, 0)

    def sql_type(self, type_):
        if type_ in self.TYPES_MAPPING:
            return self.TYPES_MAPPING[type_]
        if type_.startswith('VARCHAR'):
            return SQLType('VARCHAR', type_)
        return SQLType(type_, type_)

    def sql_format(self, type_, value):
        if type_ in ('INTEGER', 'BIGINT'):
            if (value is not None
                    and not isinstance(value, (Query, Expression))):
                value = int(value)
        return value

    def json_get(self, column, key=None):
        if key:
            column = JSONExtract(column, '$.%s' % key)
        return NullIf(JSONQuote(column), JSONQuote(Null))


def adapt_decimal(val):
    return str(val).encode()


def adapt_date(val):
    return val.isoformat()


def adapt_datetime(val):
    return val.replace(tzinfo=None).isoformat(" ")


def adapt_time(val):
    return val.isoformat()


def adapt_timedelta(val):
    return val.total_seconds()


sqlite.register_adapter(Decimal, adapt_decimal)
sqlite.register_adapter(dt.date, adapt_date)
sqlite.register_adapter(dt.datetime, adapt_datetime)
sqlite.register_adapter(dt.time, adapt_time)
sqlite.register_adapter(dt.timedelta, adapt_timedelta)


def convert_numeric(val):
    return Decimal(val.decode())


def convert_date(val):
    return dt.date.fromisoformat(val.decode())


def convert_datetime(val):
    return dt.datetime.fromisoformat(val.decode())


def convert_time(val):
    return dt.time.fromisoformat(val.decode())


def convert_interval(value):
    value = float(value)
    # It is not allowed to instatiate timedelta with the min/max total seconds
    if value >= _interval_max:
        return dt.timedelta.max
    elif value <= _interval_min:
        return dt.timedelta.min
    return dt.timedelta(seconds=value)


_interval_max = dt.timedelta.max.total_seconds()
_interval_min = dt.timedelta.min.total_seconds()


sqlite.register_converter('NUMERIC', convert_numeric)
sqlite.register_converter('DATE', convert_date)
sqlite.register_converter('DATETIME', convert_datetime)
sqlite.register_converter('TIME', convert_time)
sqlite.register_converter('TIMESTAMP', convert_datetime)
sqlite.register_converter('INTERVAL', convert_interval)
