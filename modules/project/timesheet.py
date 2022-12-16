# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = ['TimesheetWork']


class TimesheetWork(metaclass=PoolMeta):
    __name__ = 'timesheet.work'

    @classmethod
    def _get_origin(cls):
        return super(TimesheetWork, cls)._get_origin() + ['project.work']

    def _validate_company(self):
        pool = Pool()
        ProjectWork = pool.get('project.work')
        result = super(TimesheetWork, self)._validate_company()
        if isinstance(self.origin, ProjectWork):
            result &= self.company == self.origin.company
        return result
