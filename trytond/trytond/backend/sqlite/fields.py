#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend import fields


class Boolean(fields.Boolean):

    @staticmethod
    def sql_format(value):
        return value

    @staticmethod
    def sql_type(field):
        return ('BOOLEAN', 'BOOLEAN')


class Integer(fields.Integer):

    @staticmethod
    def sql_format(value):
        if value is None:
            return value
        return int(value)

    @staticmethod
    def sql_type(field):
        return ('INTEGER', 'INTEGER')


class BigInteger(fields.BigInteger, Integer):
    pass


class Char(fields.Char):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


class Sha(fields.Sha):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR(40)')


class Text(fields.Text):

    @staticmethod
    def sql_type(field):
        return ('TEXT', 'TEXT')


class Float(fields.Float):

    @staticmethod
    def sql_format(value):
        if value is None:
            return value
        return float(value)

    @staticmethod
    def sql_type(field):
        return ('FLOAT', 'FLOAT')


class Numeric(fields.Numeric):

    @staticmethod
    def sql_type(field):
        return ('NUMERIC', 'NUMERIC')


class Date(fields.Date):

    @staticmethod
    def sql_type(field):
        return ('DATE', 'DATE')


class DateTime(fields.DateTime):

    @staticmethod
    def sql_type(field):
        return ('TIMESTAMP', 'TIMESTAMP')


class Timestamp(fields.Timestamp):

    @staticmethod
    def sql_type(field):
        return ('TIMESTAMP', 'TIMESTAMP')


class Time(fields.Time):

    @staticmethod
    def sql_type(field):
        return ('TIME', 'TIME')


class Binary(fields.Binary):

    @staticmethod
    def sql_type(field):
        return ('BLOB', 'BLOB')


class Selection(fields.Selection):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


class Reference(fields.Reference):

    @staticmethod
    def sql_type(field):
        return ('VARCHAR', 'VARCHAR')


class Many2One(fields.Many2One):

    @staticmethod
    def sql_type(field):
        return ('INTEGER', 'INTEGER')


class Dict(fields.Dict):

    @staticmethod
    def sql_type(field):
        return ('TEXT', 'TEXT')

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
