# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Cast, CombiningQuery, Literal, Select

from trytond import backend

from .field import order_method
from .float import Float


class Numeric(Float):
    '''
    Define a numeric field (``decimal``).
    '''
    _type = 'numeric'
    _sql_type = 'NUMERIC'
    _py_type = Decimal

    @order_method
    def convert_order(self, name, tables, Model):
        columns = super().convert_order(name, tables, Model)
        if backend.name == 'sqlite':
            # Must be cast because Decimal is stored as bytes
            columns = [Cast(c, self.sql_type().base) for c in columns]
        return columns

    def _domain_column(self, operator, column):
        column = super()._domain_column(operator, column)
        if backend.name == 'sqlite':
            # Must be casted as Decimal is stored as bytes
            column = Cast(column, self.sql_type().base)
        return column

    def _domain_value(self, operator, value):
        value = super(Numeric, self)._domain_value(operator, value)
        if backend.name == 'sqlite':
            if isinstance(value, (Select, CombiningQuery)):
                return value
            # Must be casted as Decimal is adapted to bytes
            type_ = self.sql_type().base
            if operator in ('in', 'not in'):
                return [Cast(Literal(v), type_) for v in value]
            elif value is not None:
                return Cast(Literal(value), type_)
        return value
