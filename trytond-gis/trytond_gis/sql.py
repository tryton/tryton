# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.functions import Function

__all__ = ['ST_Equals']


class ST_Equals(Function):
    __slots__ = ()
    _function = 'ST_Equals'
