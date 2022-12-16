# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import party


def register():
    Pool.register(
        account.Configuration,
        account.ConfigurationDefaultCreditLimitAmount,
        party.Party,
        party.PartyCreditLimitAmount,
        module='account_credit_limit', type_='model')
    Pool.register(
        account.Level,
        module='account_credit_limit', type_='model',
        depends=['account_dunning'])
