# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import work
from . import routing
from . import production


def register():
    Pool.register(
        work.WorkCenterCategory,
        work.WorkCenter,
        work.Work,
        work.WorkCycle,
        routing.Operation,
        routing.RoutingStep,
        production.Production,
        module='production_work', type_='model')
