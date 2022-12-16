# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import party
from . import edocument
from . import ir

__all__ = ['register']


def register():
    Pool.register(
        account.Configuration,
        account.CredentialChorus,
        account.Invoice,
        account.InvoiceChorus,
        party.Party,
        ir.Cron,
        module='account_fr_chorus', type_='model')
    Pool.register(
        edocument.UNCEFACTInvoice,
        module='account_fr_chorus', type_='model',
        depends=['edocument_uncefact'])
    Pool.register(
        module='account_fr_chorus', type_='wizard')
    Pool.register(
        module='account_fr_chorus', type_='report')
