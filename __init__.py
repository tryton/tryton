# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .work import *
from .timesheet import *
from . import party


def register():
    Pool.register(
        Work,
        TimesheetWork,
        module='project', type_='model')
    Pool.register(
        party.PartyReplace,
        party.PartyErase,
        module='project', type_='wizard')
