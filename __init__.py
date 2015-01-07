# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .account import *
from .statement import *


def register():
    Pool.register(
        Journal,
        Payment,
        Move,
        Statement,
        StatementLine,
        module='account_payment_clearing', type_='model')
