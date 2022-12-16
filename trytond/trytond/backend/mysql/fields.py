#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend import fields


class Boolean(fields.Boolean):

    @staticmethod
    def sql_type(field):
        return ('bool', 'bool')

    @staticmethod
    def sql_format(value):
        return value


class Integer(fields.Integer):

    @staticmethod
    def sql_type(field):
        return ('bigint', 'bigint')


class BigInteger(fields.BigInteger):

    @staticmethod
    def sql_type(field):
        return ('bigint', 'bigint')


class Char(fields.Char):

    @staticmethod
    def sql_type(field):
        if isinstance(field.size, int):
            return ('varchar', 'varchar(%d)' % (field.size,))
        return ('varchar', 'varchar(255)')


class Sha(fields.Sha):

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar(40)')


class Text(fields.Text):

    @staticmethod
    def sql_type(field):
        return ('text', 'text')


class Float(fields.Float):

    @staticmethod
    def sql_type(field):
        return ('double', 'double(255, 15)')


class Numeric(fields.Numeric):

    @staticmethod
    def sql_type(field):
        return ('decimal', 'decimal(65, 30)')


class Date(fields.Date):

    @staticmethod
    def sql_type(field):
        return ('date', 'date')


class DateTime(fields.DateTime):

    @staticmethod
    def sql_type(field):
        return ('timestamp', 'timestamp null')


class Timestamp(fields.Timestamp):

    @staticmethod
    def sql_type(field):
        return ('timestamp', 'timestamp null')


class Time(fields.Time):

    @staticmethod
    def sql_type(field):
        return ('time', 'time')


class Binary(fields.Binary):

    @staticmethod
    def sql_format(value):
        return value or None

    @staticmethod
    def sql_type(field):
        return ('longblob', 'longblob')


class Selection(fields.Selection):

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar(255)')


class Reference(fields.Reference):

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar(255)')


class Many2One(fields.Many2One):

    @staticmethod
    def sql_type(field):
        return ('bigint', 'bigint')


class Dict(fields.Dict):

    @staticmethod
    def sql_type(field):
        return ('text', 'text')

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
    'timestamp': Timestamp,
    'time': Time,
    'binary': Binary,
    'selection': Selection,
    'reference': Reference,
    'many2one': Many2One,
    'one2many': fields.One2Many,
    'many2many': fields.Many2Many,
    'function': fields.Function,
    'property': fields.Property,
    'dict': Dict,
}
