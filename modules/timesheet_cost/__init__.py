# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import company
from . import timesheet


def register():
    Pool.register(
        company.Employee,
        company.EmployeeCostPrice,
        timesheet.Line,
        module='timesheet_cost', type_='model')
