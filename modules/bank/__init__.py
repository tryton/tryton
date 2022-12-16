# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import bank
from . import party


def register():
    Pool.register(
        bank.Bank,
        bank.Account,
        bank.AccountNumber,
        bank.AccountParty,
        party.Party,
        module='bank', type_='model')
    Pool.register(
        party.Replace,
        module='bank', type_='wizard')
