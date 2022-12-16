# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import account
from . import reporting_tax


def register():
    Pool.register(
        reporting_tax.PrintAEATStart,
        account.TaxCodeTemplate,
        account.TaxCode,
        module='account_es', type_='model')
    Pool.register(
        reporting_tax.AEAT111,
        reporting_tax.AEAT115,
        reporting_tax.AEAT303,
        module='account_es', type_='report')
    Pool.register(
        reporting_tax.PrintAEAT,
        module='account_es', type_='wizard')
