#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha


class Field(object):

    @staticmethod
    def sql_format(value):
        if value is None or value == False:
            return None
        elif isinstance(value, str):
            return unicode(value, 'utf-8')
        elif isinstance(value, unicode):
            return value
        return unicode(value)

    @staticmethod
    def sql_type(field):
        raise NotImplementedError


class Boolean(Field):

    @staticmethod
    def sql_format(value):
        return value and 'True' or 'False'


class Integer(Field):

    @staticmethod
    def sql_format(value):
        return int(value or 0)


class BigInteger(Integer):
    pass


class Char(Field):
    pass


class Sha(Field):

    @staticmethod
    def sql_format(value):
        if isinstance(value, basestring):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            if hashlib:
                value = hashlib.sha1(value).hexdigest()
            else:
                value = sha.new(value).hexdigest()
        return Field.sql_format(value)


class Text(Field):
    pass


class Float(Field):

    @staticmethod
    def sql_format(value):
        return float(value or 0.0)


class Numeric(Float):

    @staticmethod
    def sql_format(value):
        if not value:
            value = Decimal('0.0')
        if isinstance(value, (int, long)):
            value = Decimal(str(value))
        if isinstance(value, float) and hasattr(value, 'decimal'):
            value = value.decimal
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
        if isinstance(value, datetime.datetime):
            value = value.date()
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
    pass


class Binary(Field):

    @staticmethod
    def sql_format(value):
        return value or None


class Selection(Char):
    pass


class Reference(Field):
    pass


class Many2One(Field):

    @staticmethod
    def sql_format(value):
        return value and int(value) or None


class One2Many(Field):
    pass


class Many2Many(Field):
    pass


class Function(Field):
    pass


class Property(Function):
    pass
