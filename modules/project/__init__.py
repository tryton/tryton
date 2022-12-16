# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import ir, party, timesheet, work


def register():
    Pool.register(
        # Before Work because status default value is read from WorkStatus
        work.WorkStatus,
        work.Work,
        timesheet.Line,
        timesheet.Work,
        ir.ActWindow,
        module='project', type_='model')
    Pool.register(
        party.Replace,
        party.Erase,
        module='project', type_='wizard')
