# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import analytic_account


def register():
    Pool.register(
        analytic_account.BudgetContext,
        analytic_account.Budget,
        analytic_account.BudgetLine,
        analytic_account.CopyBudgetStart,
        module='analytic_budget', type_='model')
    Pool.register(
        analytic_account.CopyBudget,
        module='analytic_budget', type_='wizard')
