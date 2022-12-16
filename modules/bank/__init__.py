# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .bank import *
from .party import *


def register():
    Pool.register(
        Bank,
        BankAccount,
        BankAccountNumber,
        BankAccountParty,
        Party,
        module='bank', type_='model')
    Pool.register(
        PartyReplace,
        module='bank', type_='wizard')
