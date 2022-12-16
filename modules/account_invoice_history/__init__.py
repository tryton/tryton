# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import account
from . import account_invoice


def register():
    Pool.register(
        party.Party,
        party.Address,
        account.Invoice,
        account_invoice.PaymentTerm,
        account_invoice.PaymentTermLine,
        account_invoice.PaymentTermLineRelativeDelta,
        module='account_invoice_history', type_='model')
