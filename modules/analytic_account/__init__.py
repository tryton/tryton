# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .line import *


def register():
    Pool.register(
        Account,
        OpenChartAccountStart,
        AnalyticAccountEntry,
        Line,
        Move,
        MoveLine,
        module='analytic_account', type_='model')
    Pool.register(
        OpenChartAccount,
        OpenAccount,
        module='analytic_account', type_='wizard')
