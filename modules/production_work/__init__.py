# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .work import *
from .routing import *
from .production import *


def register():
    Pool.register(
        WorkCenterCategory,
        WorkCenter,
        Work,
        WorkCycle,
        Operation,
        RoutingStep,
        Production,
        module='production_work', type_='model')
