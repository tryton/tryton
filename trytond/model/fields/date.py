# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from sql import Query, Expression

from ... import backend
from .field import Field, SQLType


class Date(Field):
    '''
    Define a date field (``date``).
    '''
    _type = 'date'

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        if isinstance(value, basestring):
            year, month, day = map(int, value.split("-", 2))
            return datetime.date(year, month, day)

        assert(isinstance(value, datetime.date))
        # Allow datetime with min time for XML-RPC
        # datetime must be tested separately because datetime is a
        # subclass of date
        assert(not isinstance(value, datetime.datetime)
            or value.time() == datetime.time())
        return value

    def sql_type(self):
        return SQLType('DATE', 'DATE')


class DateTime(Field):
    '''
    Define a datetime field (``datetime``).
    '''
    _type = 'datetime'

    def __init__(self, string='', format='%H:%M:%S', help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param format: The validation format as used by strftime.
        '''
        super(DateTime, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.format = format

    __init__.__doc__ += Field.__init__.__doc__

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if not value:
            return None
        if isinstance(value, basestring):
            datepart, timepart = value.split(" ")
            year, month, day = map(int, datepart.split("-", 2))
            hours, minutes, seconds = map(int, timepart.split(":"))
            return datetime.datetime(year, month, day, hours, minutes, seconds)
        assert(isinstance(value, datetime.datetime))
        return value.replace(microsecond=0)

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'sqlite':
            return SQLType('TIMESTAMP', 'TIMESTAMP')
        elif db_type == 'mysql':
            return SQLType('TIMESTAMP', 'TIMESTAMP NULL')
        return SQLType('TIMESTAMP', 'TIMESTAMP(0)')


class Timestamp(Field):
    '''
    Define a timestamp field (``datetime``).
    '''
    _type = 'timestamp'

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        if isinstance(value, basestring):
            datepart, timepart = value.split(" ")
            year, month, day = map(int, datepart.split("-", 2))
            timepart_full = timepart.split(".", 1)
            hours, minutes, seconds = map(int, timepart_full[0].split(":"))
            if len(timepart_full) == 2:
                microseconds = int(timepart_full[1])
            else:
                microseconds = 0
            return datetime.datetime(year, month, day, hours, minutes, seconds,
                    microseconds)
        assert(isinstance(value, datetime.datetime))
        return value

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'sqlite':
            return SQLType('TIMESTAMP', 'TIMESTAMP')
        elif db_type == 'mysql':
            return SQLType('TIMESTAMP', 'TIMESTAMP NULL')
        return SQLType('TIMESTAMP', 'TIMESTAMP(6)')


class Time(DateTime):
    '''
    Define a time field (``time``).
    '''
    _type = 'time'

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        if isinstance(value, basestring):
            hours, minutes, seconds = map(int, value.split(":"))
            return datetime.time(hours, minutes, seconds)
        assert(isinstance(value, datetime.time))
        return value.replace(microsecond=0)

    def sql_type(self):
        return SQLType('TIME', 'TIME')


class TimeDelta(Field):
    '''
    Define a timedelta field (``timedelta``).
    '''
    _type = 'timedelta'

    def __init__(self, string='', converter=None, help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param converter: The name of the context key containing
            the time converter.
        '''
        super(TimeDelta, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.converter = converter

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        assert(isinstance(value, datetime.timedelta))
        db_type = backend.name()
        if db_type == 'mysql':
            return value.total_seconds()
        return value

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'mysql':
            return SQLType('DOUBLE', 'DOUBLE(255, 6)')
        return SQLType('INTERVAL', 'INTERVAL')

    @classmethod
    def get(cls, ids, model, name, values=None):
        result = {}
        for row in values:
            value = row[name]
            if (value is not None
                    and not isinstance(value, datetime.timedelta)):
                if value >= datetime.timedelta.max.total_seconds():
                    value = datetime.timedelta.max
                elif value <= datetime.timedelta.min.total_seconds():
                    value = datetime.timedelta.min
                else:
                    value = datetime.timedelta(seconds=value)
                result[row['id']] = value
            else:
                result[row['id']] = value
        return result
