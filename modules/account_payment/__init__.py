# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import payment
from . import account
from . import party


def register():
    Pool.register(
        payment.Journal,
        payment.Group,
        payment.Payment,
        account.MoveLine,
        payment.ProcessPaymentStart,
        account.PayLineStart,
        account.PayLineAskJournal,
        account.Configuration,
        account.ConfigurationPaymentGroupSequence,
        party.Party,
        party.PartyPaymentDirectDebit,
        module='account_payment', type_='model')
    Pool.register(
        account.Invoice,
        module='account_payment', type_='model', depends=['account_invoice'])
    Pool.register(
        payment.ProcessPayment,
        account.PayLine,
        party.Replace,
        party.Erase,
        module='account_payment', type_='wizard')
