# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .work import *
from .line import *


def register():
    Pool.register(
        Work,
        OpenWorkStart,
        Line,
        EnterLinesStart,
        HoursEmployee,
        OpenHoursEmployeeStart,
        HoursEmployeeWeekly,
        HoursEmployeeMonthly,
        module='timesheet', type_='model')
    Pool.register(
        OpenWork,
        OpenWork2,
        OpenWorkGraph,
        EnterLines,
        OpenHoursEmployee,
        module='timesheet', type_='wizard')
