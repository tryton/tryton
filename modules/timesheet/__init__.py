# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import work
from . import line
from . import user
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        work.Work,
        work.WorkContext,
        line.Line,
        line.EnterLinesStart,
        line.HoursEmployee,
        line.HoursEmployeeContext,
        line.HoursEmployeeWeekly,
        line.HoursEmployeeMonthly,
        user.UserApplication,
        module='timesheet', type_='model')
    Pool.register(
        line.EnterLines,
        module='timesheet', type_='wizard')
