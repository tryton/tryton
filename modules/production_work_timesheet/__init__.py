# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .work import *
from .routing import *
from .timesheet import *


def register():
    Pool.register(
        Work,
        Operation,
        TimesheetWork,
        module='production_work_timesheet', type_='model')
