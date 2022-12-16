#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
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
        return None


class Boolean(Field):

    @staticmethod
    def sql_format(value):
        return value and '1' or '0'

    @staticmethod
    def sql_type(field):
        return ('BOOLEAN', 'BOOLEAN')


class Integer(Field):

    @staticmethod
    def sql_format(value):
        return int(value or 0)

    @staticmethod
    def sql_type(field):
        return ('INTEGER', 'INTEGER')


class BigInteger(Integer):

    @staticmethod
    def sql_type(field):
        return ('INTEGER', 'INTEGER')


class Char(Field):


    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


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

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR(40)')


class Text(Field):

    @staticmethod
    def sql_type(field):
        return ('TEXT', 'TEXT')


class Float(Field):

    @staticmethod
    def sql_format(value):
        return float(value or 0.0)

    @staticmethod
    def sql_type(field):
        return ('FLOAT', 'FLOAT')


class Numeric(Float):

    @staticmethod
    def sql_type(field):
        return ('NUMERIC', 'NUMERIC')


class Date(Field):

    @staticmethod
    def sql_format(value):
        return value or None

    @staticmethod
    def sql_type(field):
        return ('DATE', 'DATE')


class DateTime(Field):

    @staticmethod
    def sql_format(value):
        return value or None

    @staticmethod
    def sql_type(field):
        return ('TIMESTAMP', 'TIMESTAMP')


class Time(Field):

    @staticmethod
    def sql_type(field):
        return ('TIME', 'TIME')


class Binary(Field):

    @staticmethod
    def sql_format(value):
        return value or None

    @staticmethod
    def sql_type(field):
        return ('BLOB', 'BLOB')


class Selection(Char):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


class Reference(Field):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


class Many2One(Field):

    @staticmethod
    def sql_format(value):
        return value and int(value) or None

    @staticmethod
    def sql_type(field):
        return ('INTEGER', 'INTEGER')


class One2Many(Field):
    pass


class Many2Many(Field):
    pass


class Function(Field):
    pass


class Property(Function):
    pass


FIELDS = {
    'boolean': Boolean,
    'integer': Integer,
    'biginteger': BigInteger,
    'char': Char,
    'sha': Sha,
    'text': Text,
    'float': Float,
    'numeric': Numeric,
    'date': Date,
    'datetime': DateTime,
    'time': Time,
    'binary': Binary,
    'selection': Selection,
    'reference': Reference,
    'many2one': Many2One,
    'one2many': One2Many,
    'many2many': Many2Many,
    'function': Function,
    'property': Property,
}
