#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
import hashlib
try:
    import simplejson as json
except ImportError:
    import json


class Field(object):

    @staticmethod
    def sql_format(value):
        return value

    @staticmethod
    def sql_type(field):
        raise NotImplementedError


class Boolean(Field):
    pass


class Integer(Field):
    pass


class BigInteger(Integer):
    pass


class Char(Field):

    @staticmethod
    def sql_format(value):
        if value is None:
            return None
        elif isinstance(value, str):
            return unicode(value, 'utf-8')
        assert isinstance(value, unicode)
        return value


class Sha(Field):

    @staticmethod
    def sql_format(value):
        if value is not None:
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            value = hashlib.sha1(value).hexdigest()
        return Char.sql_format(value)


class Text(Char):
    pass


class Float(Field):
    pass


class Numeric(Float):

    @staticmethod
    def sql_format(value):
        if value is None:
            return value
        if isinstance(value, (int, long)):
            value = Decimal(str(value))
        assert isinstance(value, Decimal)
        return value


class Date(Field):

    @staticmethod
    def sql_format(value):
        if not value:
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


class DateTime(Field):

    @staticmethod
    def sql_format(value):
        if not value:
            return None
        if isinstance(value, basestring):
            datepart, timepart = value.split(" ")
            year, month, day = map(int, datepart.split("-", 2))
            hours, minutes, seconds = map(int, timepart.split(":"))
            return datetime.datetime(year, month, day, hours, minutes, seconds)
        assert(isinstance(value, datetime.datetime))
        return value.replace(microsecond=0)


class Timestamp(Field):

    @staticmethod
    def sql_format(value):
        if not value:
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


class Time(Field):

    @staticmethod
    def sql_format(value):
        if not value:
            return None
        if isinstance(value, basestring):
            hours, minutes, seconds = map(int, value.split(":"))
            return datetime.time(hours, minutes, seconds)
        assert(isinstance(value, datetime.time))
        return value.replace(microsecond=0)


class Binary(Field):
    pass


class Selection(Char):
    pass


class Reference(Char):

    @staticmethod
    def sql_format(value):
        if not isinstance(value, basestring):
            try:
                value = '%s,%s' % tuple(value)
            except TypeError:
                pass
        return Char.sql_format(value)


class Many2One(Field):

    @staticmethod
    def sql_format(value):
        if value is None:
            return None
        assert value is not False
        return int(value)


class One2Many(Field):
    pass


class Many2Many(Field):
    pass


class Function(Field):
    pass


class Property(Function):
    pass


class Dict(Field):

    @staticmethod
    def sql_format(value):
        from trytond.protocols.jsonrpc import JSONEncoder
        if value is None:
            return None
        assert isinstance(value, dict)
        return json.dumps(value, cls=JSONEncoder)
