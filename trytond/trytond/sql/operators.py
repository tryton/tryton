# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Expression, Literal, Null
from sql.conditionals import Case
from sql.operators import BinaryOperator

from trytond.transaction import Transaction

from .functions import Range

__all__ = ['RangeContain', 'RangeIn', 'RangeOverlap']


def _has_range():
    return Transaction().database.has_range()


class RangeOperator(BinaryOperator):
    __slots__ = ()

    def __str__(self):
        if not _has_range():
            return str(self._sql_expression)
        return super().__str__()

    @property
    def params(self):
        if not _has_range():
            return self._sql_expression.params
        return super().params


class RangeContain(RangeOperator):
    __slots__ = ()
    _operator = '@>'

    @property
    def _sql_expression(self):
        lower1, upper1, bounds1 = self.left.args
        if isinstance(self.right, Range):
            lower2, upper2, bounds2 = self.right.args
        else:
            lower2 = upper2 = self.right
            bounds2 = '[]'

        if not isinstance(lower1, Expression):
            lower1 = Literal(lower1)
        if not isinstance(upper1, Expression):
            upper1 = Literal(upper1)
        if not isinstance(lower2, Expression):
            lower2 = Literal(lower2)
        if not isinstance(upper2, Expression):
            upper2 = Literal(upper2)

        if bounds1[0] == '(' and bounds2[0] == '[':
            expression1 = lower1 < lower2
        else:
            expression1 = lower1 <= lower2
        expression1 = Case(
            ((lower1 == Null), True),
            ((lower2 == Null), False),
            else_=expression1)
        if bounds1[1] == ')' and bounds2[1] == ']':
            expression2 = upper1 > upper2
        else:
            expression2 = upper1 >= upper2
        expression2 = Case(
            ((upper1 == Null), True),
            ((upper2 == Null), False),
            else_=expression2)
        return (expression1) & (expression2)


class RangeIn(RangeOperator):
    __slots__ = ()
    _operator = '<@'

    @property
    def _sql_expression(self):
        return RangeContain(self.right, self.left)._sql_expression


class RangeOverlap(RangeOperator):
    __slots__ = ()
    _operator = '&&'

    @property
    def _sql_expression(self):
        lower1, upper1, bounds1 = self.left.args
        lower2, upper2, bounds2 = self.right.args

        if not isinstance(lower1, Expression):
            lower1 = Literal(lower1)
        if not isinstance(upper1, Expression):
            upper1 = Literal(upper1)
        if not isinstance(lower2, Expression):
            lower2 = Literal(lower2)
        if not isinstance(upper2, Expression):
            upper2 = Literal(upper2)

        if bounds1[0] == '[' and bounds2[1] == ']':
            expression1 = lower1 <= upper2
        else:
            expression1 = lower1 < upper2
        expression1 = Case(
            ((lower1 == Null) | (upper2 == Null), True),
            else_=expression1)
        if bounds1[1] == ']' and bounds2[0] == '[':
            expression2 = lower2 <= upper1
        else:
            expression2 = lower2 < upper1
        expression2 = Case(
            ((lower2 == Null) | (upper1 == Null), True),
            else_=expression2)
        return (expression1) & (expression2)
