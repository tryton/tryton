# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.TaxTemplate,
        account.Tax,
        account.ECSalesList,
        account.ECSalesListContext,
        module='account_eu', type_='model')
