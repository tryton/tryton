# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import work
from . import routing
from . import timesheet


def register():
    Pool.register(
        work.Work,
        routing.Operation,
        timesheet.Work,
        module='production_work_timesheet', type_='model')
