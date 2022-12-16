# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account, ir, party

__all__ = ['register']


def register():
    Pool.register(
        ir.Cron,
        account.Configuration,
        account.CredentialSII,
        account.TaxTemplate,
        account.Tax,
        account.FiscalYear,
        account.Period,
        account.Invoice,
        account.InvoiceSII,
        party.Identifier,
        module='account_es_sii', type_='model')
