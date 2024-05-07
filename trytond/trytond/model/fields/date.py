# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.functions import AtTimeZone, Function

from trytond import backend
from trytond.pyson import PYSON, PYSONEncoder
from trytond.tools import cached_property

from .field import Field, get_eval_fields


class SQLite_Date(Function):
    __slots__ = ()
    _function = 'DATE'


class SQLite_DateTime(Function):
    __slots__ = ()
    _function = 'DATETIME'


class SQLite_Time(Function):
    __slots__ = ()
    _function = 'TIME'


class Date(Field):
    '''
    Define a date field (``date``).
    '''
    _type = 'date'
    _sql_type = 'DATE'
    _py_type = datetime.date

    def sql_format(self, value):
        if isinstance(value, str):
            value = datetime.date.fromisoformat(value)
        elif isinstance(value, datetime.datetime):
            raise ValueError("Date field can not have time")
        return super().sql_format(value)

    def sql_cast(self, expression, timezone=None):
        if backend.name == 'sqlite':
            return SQLite_Date(expression)
        if timezone:
            expression = AtTimeZone(expression, 'utc')
            expression = AtTimeZone(expression, timezone)
        return super(Date, self).sql_cast(expression)


class FormatMixin(Field):

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        definition['format'] = encoder.encode(self.format)
        return definition

    @cached_property
    def display_depends(self):
        depends = super().display_depends
        if isinstance(self.format, PYSON):
            depends |= get_eval_fields(self.format)
        return depends

    @cached_property
    def validation_depends(self):
        depends = super().display_depends
        if isinstance(self.format, PYSON):
            depends |= get_eval_fields(self.format)
        return depends


class Timestamp(FormatMixin, Field):
    '''
    Define a timestamp field (``datetime``).
    '''
    _type = 'timestamp'
    _sql_type = 'TIMESTAMP'
    _py_type = datetime.datetime
    format = '%H:%M:%S.%f'

    def sql_format(self, value):
        if isinstance(value, str):
            value = datetime.datetime.fromisoformat(value)
        return super().sql_format(value)

    def sql_cast(self, expression):
        if backend.name == 'sqlite':
            return SQLite_DateTime(expression)
        return super().sql_cast(expression)


class DateTime(Timestamp):
    '''
    Define a datetime field (``datetime``).
    '''
    _type = 'datetime'
    _sql_type = 'DATETIME'

    def __init__(self, string='', format='%H:%M:%S', help='', required=False,
            readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param format: The validation format as used by strftime.
        '''
        super(DateTime, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.format = format

    __init__.__doc__ += Field.__init__.__doc__

    def sql_format(self, value):
        value = super().sql_format(value)
        if isinstance(value, datetime.datetime):
            value = value.replace(microsecond=0)
        return value


class Time(FormatMixin, Field):
    '''
    Define a time field (``time``).
    '''
    _type = 'time'
    _sql_type = 'TIME'
    _py_type = datetime.time

    def __init__(self, string='', format='%H:%M:%S', help='', required=False,
            readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param format: The validation format as used by strftime.
        '''
        super().__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.format = format

    def sql_format(self, value):
        if isinstance(value, str):
            value = datetime.time.fromisoformat(value)
        value = super().sql_format(value)
        if isinstance(value, datetime.time):
            value = value.replace(microsecond=0)
        return value

    def sql_cast(self, expression):
        if backend.name == 'sqlite':
            return SQLite_Time(expression)
        return super(Time, self).sql_cast(expression)


class TimeDelta(Field):
    '''
    Define a timedelta field (``timedelta``).
    '''
    _type = 'timedelta'
    _sql_type = 'INTERVAL'
    _py_type = datetime.timedelta

    def __init__(self, string='', converter=None, help='', required=False,
            readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param converter: The name of the context key containing
            the time converter.
        '''
        super(TimeDelta, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.converter = converter

    def sql_format(self, value):
        if isinstance(value, (int, float)):
            value = datetime.timedelta(seconds=value)
        elif isinstance(value, str):
            if not value.find(':'):
                raise ValueError(
                    "TimeDelta requires a string '%H:%M:%S.%f' or '%H:%M'")
            hours, minutes, seconds = (value.split(":") + ['00'])[:3]
            value = datetime.timedelta(
                hours=int(hours), minutes=int(minutes), seconds=float(seconds))
        return super().sql_format(value)

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

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['converter'] = self.converter
        return definition
