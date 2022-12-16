# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import work
from . import timesheet
from . import party


def register():
    Pool.register(
        work.Work,
        timesheet.Line,
        timesheet.Work,
        module='project', type_='model')
    Pool.register(
        party.PartyReplace,
        party.PartyErase,
        module='project', type_='wizard')
