# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import ir
from . import party
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        ir.Cron,
        account.PaymentJournal,
        account.PaymentGroup,
        account.Payment,
        account.PaymentBraintreeRefund,
        account.PaymentBraintreeAccount,
        account.PaymentBraintreeCustomer,
        account.PaymentBraintreeCustomerPaymentMethodDeleteAsk,
        party.Party,
        module='account_payment_braintree', type_='model')
    Pool.register(
        account.PaymentBraintreeCustomerPaymentMethodDelete,
        account.PaymentBraintreeCheckout,
        party.Replace,
        module='account_payment_braintree', type_='wizard')
    Pool.register(
        account.PaymentBraintreeCheckoutPage,
        module='account_payment_braintree', type_='report')
