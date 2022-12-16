# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .account import *
from .party import PartyReplace


def register():
    Pool.register(
        Journal,
        Group,
        Payment,
        MoveLine,
        ProcessPaymentStart,
        PayLineAskJournal,
        Configuration,
        Invoice,
        module='account_payment', type_='model')
    Pool.register(
        ProcessPayment,
        PayLine,
        PartyReplace,
        module='account_payment', type_='wizard')
