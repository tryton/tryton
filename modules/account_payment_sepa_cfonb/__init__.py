# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import payment


def register():
    Pool.register(
        payment.Journal,
        payment.Group,
        module='account_payment_sepa_cfonb', type_='model')
