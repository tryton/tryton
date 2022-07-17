# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import ir, party, payment, routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        payment.Account,
        payment.Refund,
        payment.Customer,
        payment.CustomerFingerprint,
        payment.CustomerIdentical,
        payment.Journal,
        payment.Group,
        payment.Payment,
        payment.CustomerSourceDetachAsk,
        party.Party,
        party.PartyReceptionDirectDebit,
        ir.Cron,
        module='account_payment_stripe', type_='model')
    Pool.register(
        payment.Checkout,
        payment.CustomerSourceDetach,
        party.Replace,
        module='account_payment_stripe', type_='wizard')
    Pool.register(
        payment.CheckoutPage,
        module='account_payment_stripe', type_='report')
