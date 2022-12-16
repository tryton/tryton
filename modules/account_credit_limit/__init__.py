# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from account import *
from party import *


def register():
    Pool.register(
        Configuration,
        Level,
        Party,
        module='account_credit_limit', type_='model')
