# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .line import *
from . import rule


def register():
    Pool.register(
        Account,
        AccountDistribution,
        OpenChartAccountStart,
        AnalyticAccountEntry,
        Line,
        Move,
        MoveLine,
        rule.Rule,
        module='analytic_account', type_='model')
    Pool.register(
        OpenChartAccount,
        OpenAccount,
        module='analytic_account', type_='wizard')
