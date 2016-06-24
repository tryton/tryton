# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .work import *
from .line import *


def register():
    Pool.register(
        Work,
        WorkContext,
        Line,
        EnterLinesStart,
        HoursEmployee,
        HoursEmployeeContext,
        HoursEmployeeWeekly,
        HoursEmployeeMonthly,
        module='timesheet', type_='model')
    Pool.register(
        EnterLines,
        module='timesheet', type_='wizard')
