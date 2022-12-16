# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account


def register():
    Pool.register(
        account.Type,
        account.Move,
        account.MoveLine,
        account.Consolidation,
        account.ConsolidationBalanceSheetContext,
        account.ConsolidationIncomeStatementContext,
        module='account_consolidation', type_='model')
    Pool.register(
        account.ConsolidationStatement,
        module='account_consolidation', type_='report')
    Pool.register(
        account.Invoice,
        module='account_consolidation', type_='model',
        depends=['account_invoice'])
