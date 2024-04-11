# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, party

__all__ = ['register']


def register():
    Pool.register(
        party.Configuration,
        party.Party,
        party.Identifier,
        account.Account,
        account.FiscalYear,
        account.Period,
        account.Journal,
        account.Move,
        account.MoveLine,
        account.TaxTemplate,
        account.Tax,
        account.TaxLine,
        account.MoveExport,
        module='account_export_winbooks', type_='model')
    Pool.register(
        account.RenewFiscalYear,
        module='account_export_winbooks', type_='wizard')
