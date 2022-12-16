# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Query, Expression

from ... import backend
from .field import Field, SQLType


class Integer(Field):
    '''
    Define an integer field (``int``).
    '''
    _type = 'integer'

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'postgresql':
            return SQLType('INT4', 'INT4')
        elif db_type == 'mysql':
            return SQLType('SIGNED INTEGER', 'BIGINT')
        else:
            return SQLType('INTEGER', 'INTEGER')

    def sql_format(self, value):
        db_type = backend.name()
        if (db_type == 'sqlite'
                and value is not None
                and not isinstance(value, (Query, Expression))):
            value = int(value)
        return super(Integer, self).sql_format(value)


class BigInteger(Integer):
    '''
    Define an integer field (``long``).
    '''
    _type = 'biginteger'

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'postgresql':
            return SQLType('INT8', 'INT8')
        return super(BigInteger, self).sql_type()
