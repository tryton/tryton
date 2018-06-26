# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Company', 'Employee']


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'
    _history = True


class Employee(metaclass=PoolMeta):
    __name__ = 'company.employee'
    _history = True
