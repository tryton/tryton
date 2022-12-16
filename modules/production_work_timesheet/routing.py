# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Operation']


class Operation(metaclass=PoolMeta):
    __name__ = 'production.routing.operation'

    timesheet_available = fields.Boolean('Available on timesheets')

    @classmethod
    def default_timesheet_available(cls):
        return False
