# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import payment
from . import party
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        payment.Account,
        payment.Customer,
        payment.Journal,
        payment.Group,
        payment.Payment,
        party.Party,
        module='account_payment_stripe', type_='model')
    Pool.register(
        payment.Checkout,
        module='account_payment_stripe', type_='wizard')
    Pool.register(
        payment.CheckoutPage,
        module='account_payment_stripe', type_='report')
