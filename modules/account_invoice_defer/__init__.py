# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.ConfigurationDefaultAccount,
        account.InvoiceDeferred,
        account.Move,
        account.Period,
        account.Invoice,
        account.InvoiceLine,
        module='account_invoice_defer', type_='model')
    Pool.register(
        account.InvoiceDeferredCreateMoves,
        module='account_invoice_defer', type_='wizard')
    Pool.register(
        module='account_invoice_defer', type_='report')
