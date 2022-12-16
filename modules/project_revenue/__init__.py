#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .service import *
from .work import *


def register():
    Pool.register(
        Employee,
        EmployeeCostPrice,
        TimesheetLine,
        Work,
        module='project_revenue', type_='model')
