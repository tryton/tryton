# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from .field import Field


class Integer(Field):
    '''
    Define an integer field (``int``).
    '''
    _type = 'integer'
    _sql_type = 'INTEGER'

    def sql_format(self, value):
        if value is None:
            return None
        return int(str(value))


class BigInteger(Integer):
    '''
    Define an integer field (``long``).
    '''
    _type = 'biginteger'
    _sql_type = 'BIGINT'
