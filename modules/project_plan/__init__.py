# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import allocation
from . import work


def register():
    Pool.register(
        allocation.Allocation,
        work.Work,
        work.PredecessorSuccessor,
        module='project_plan', type_='model')
    Pool.register(
        work.Leveling,
        module='project_plan', type_='wizard')
