# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Company', 'Employee']


class Company:
    __metaclass__ = PoolMeta
    __name__ = 'company.company'
    _history = True


class Employee:
    __metaclass__ = PoolMeta
    __name__ = 'company.employee'
    _history = True
