# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.DunningLevel,
        account.Dunning,
        account.DunningEmailLog,
        module='account_dunning_email', type_='model')
    Pool.register(
        account.ProcessDunning,
        module='account_dunning_email', type_='wizard')
    Pool.register(
        module='account_dunning_email', type_='report')
