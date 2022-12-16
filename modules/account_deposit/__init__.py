# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import invoice
from . import party


def register():
    Pool.register(
        account.AccountTypeTemplate,
        account.AccountType,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.DepositRecallStart,
        party.Party,
        module='account_deposit', type_='model')
    Pool.register(
        account.Reconcile,
        invoice.DepositRecall,
        party.Erase,
        module='account_deposit', type_='wizard')
