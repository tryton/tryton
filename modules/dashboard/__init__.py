#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .dashboard import *
from .res import *
from .ir import *


def register():
    Pool.register(
        DashboardAction,
        User,
        View,
        module='dashboard', type_='model')
