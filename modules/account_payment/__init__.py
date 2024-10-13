# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account, party, payment


def register():
    Pool.register(
        payment.Journal,
        payment.Group,
        payment.Payment,
        account.MoveLine,
        account.CreateDirectDebitStart,
        account.PayLineStart,
        account.PayLineAskJournal,
        account.Configuration,
        account.ConfigurationPaymentSequence,
        account.ConfigurationPaymentGroupSequence,
        party.Party,
        party.PartyPaymentDirectDebit,
        party.PartyReceptionDirectDebit,
        module='account_payment', type_='model')
    Pool.register(
        account.Invoice,
        module='account_payment', type_='model', depends=['account_invoice'])
    Pool.register(
        account.Statement,
        account.StatementLine,
        module='account_payment', type_='model', depends=['account_statement'])
    Pool.register(
        account.StatementRule,
        account.StatementRuleLine,
        module='account_payment', type_='model',
        depends=['account_statement_rule'])
    Pool.register(
        account.Dunning,
        module='account_payment', type_='model', depends=['account_dunning'])
    Pool.register(
        payment.ProcessPayment,
        account.CreateDirectDebit,
        account.PayLine,
        account.MoveCancel,
        account.MoveLineGroup,
        account.MoveLineReschedule,
        account.MoveLineDelegate,
        party.Replace,
        party.Erase,
        module='account_payment', type_='wizard')
