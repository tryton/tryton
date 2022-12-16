# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .company import *
from .timesheet import *


def register():
    Pool.register(
        Employee,
        EmployeeCostPrice,
        TimesheetLine,
        module='timesheet_cost', type_='model')
