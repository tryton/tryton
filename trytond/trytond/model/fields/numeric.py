#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from sql import Query, Expression

from ...config import CONFIG
from .field import SQLType
from .float import Float


class Numeric(Float):
    '''
    Define a numeric field (``decimal``).
    '''
    _type = 'numeric'

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        if isinstance(value, (int, long)):
            value = Decimal(str(value))
        assert isinstance(value, Decimal)
        return value

    def sql_type(self):
        db_type = CONFIG['db_type']
        if db_type == 'mysql':
            return SQLType('DECIMAL', 'DECIMAL(65, 30)')
        return SQLType('NUMERIC', 'NUMERIC')
