# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import party

__all__ = ['register']


def register():
    Pool.register(
        account.FiscalYear,
        account.Period,
        party.Party,
        account.TaxGroupCash,
        account.Tax,
        account.TaxLine,
        account.Move,
        account.Invoice,
        account.InvoiceTax,
        account.InvoiceTaxGroupCash,
        module='account_tax_cash', type_='model')
    Pool.register(
        module='account_tax_cash', type_='wizard')
    Pool.register(
        module='account_tax_cash', type_='report')
