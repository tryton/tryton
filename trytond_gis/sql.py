from __future__ import absolute_import

from sql.functions import Function

__all__ = ['ST_Equals']


class ST_Equals(Function):
    __slots__ = ()
    _function = 'ST_Equals'
