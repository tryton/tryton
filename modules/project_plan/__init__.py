# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .allocation import *
from .work import *


def register():
    Pool.register(
        Allocation,
        Work,
        PredecessorSuccessor,
        module='project_plan', type_='model')
    Pool.register(
        Leveling,
        module='project_plan', type_='wizard')
