# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account


def register():
    Pool.register(
        account.TaxTemplate,
        account.TaxRuleTemplate,
        account.FrFECStart,
        account.FrFECResult,
        module='account_fr', type_='model')
    Pool.register(
        account.FrFEC,
        module='account_fr', type_='wizard')
