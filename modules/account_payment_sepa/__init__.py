# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account, party, payment


def register():
    Pool.register(
        payment.Journal,
        payment.Group,
        payment.Mandate,
        payment.Payment,
        payment.Message,
        party.Party,
        party.PartyReceptionDirectDebit,
        party.PartyIdentifier,
        account.Configuration,
        account.ConfigurationSepaMandateSequence,
        module='account_payment_sepa', type_='model')
    Pool.register(
        party.Replace,
        module='account_payment_sepa', type_='wizard')
    Pool.register(
        payment.MandateReport,
        module='account_payment_sepa', type_='report')
