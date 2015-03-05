# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .invoice import *
from .party import *


def register():
    Pool.register(
        AccountTemplate,
        Account,
        Invoice,
        InvoiceLine,
        DepositRecallStart,
        Party,
        module='account_deposit', type_='model')
    Pool.register(
        DepositRecall,
        module='account_deposit', type_='wizard')
