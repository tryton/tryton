#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .party import *


def register():
    Pool.register(
        Journal,
        Group,
        Mandate,
        Payment,
        Party,
        module='account_payment_sepa', type_='model')
