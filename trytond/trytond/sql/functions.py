# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.functions import Function

__all__ = ['NumRange', 'TSRange', 'DateRange']


class Range(Function):
    __slots__ = ()

    def __init__(self, lower, upper, bounds='[)'):
        assert bounds in {'()', '(]', '[)', '[]'}
        super().__init__(lower, upper, bounds)


class NumRange(Range):
    __slots__ = ()
    _function = 'NUMRANGE'


class TSRange(Range):
    __slots__ = ()
    _function = 'TSRANGE'


class DateRange(Range):
    __slots__ = ()
    _function = 'DATERANGE'
