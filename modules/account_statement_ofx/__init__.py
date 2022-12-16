# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.StatementImportStart,
        module='account_statement_ofx', type_='model')
    Pool.register(
        account.StatementImport,
        module='account_statement_ofx', type_='wizard')
    Pool.register(
        module='account_statement_ofx', type_='report')
