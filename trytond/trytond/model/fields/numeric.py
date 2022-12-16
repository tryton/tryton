# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from sql import Cast, Literal, Select, CombiningQuery, As

from trytond import backend
from .float import Float


class SQLite_Cast(Cast):

    def as_(self, output_name):
        # Use PARSE_COLNAMES instead of CAST for final column
        return As(self.expression, '%s [NUMERIC]' % output_name)


class Numeric(Float):
    '''
    Define a numeric field (``decimal``).
    '''
    _type = 'numeric'
    _sql_type = 'NUMERIC'
    _py_type = Decimal

    def sql_column(self, table):
        column = super(Numeric, self).sql_column(table)
        db_type = backend.name
        if db_type == 'sqlite':
            # Must be casted as Decimal is stored as bytes
            column = SQLite_Cast(column, self.sql_type().base)
        return column

    def _domain_value(self, operator, value):
        value = super(Numeric, self)._domain_value(operator, value)
        db_type = backend.name
        if db_type == 'sqlite':
            if isinstance(value, (Select, CombiningQuery)):
                return value
            # Must be casted as Decimal is adapted to bytes
            type_ = self.sql_type().base
            if operator in ('in', 'not in'):
                return [Cast(Literal(v), type_) for v in value]
            elif value is not None:
                return Cast(Literal(value), type_)
        return value
