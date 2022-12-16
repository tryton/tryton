# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .party import *
from .account import *


def register():
    Pool.register(
        Journal,
        Group,
        Mandate,
        Payment,
        Message,
        Party,
        PartyIdentifier,
        Configuration,
        ConfigurationSepaMandateSequence,
        module='account_payment_sepa', type_='model')
    Pool.register(
        MandateReport,
        module='account_payment_sepa', type_='report')
