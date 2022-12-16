# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account
from .account import (
    BudgetLineMixin, BudgetMixin, CopyBudgetMixin, CopyBudgetStartMixin)

__all__ = [
    'BudgetMixin', 'BudgetLineMixin',
    'CopyBudgetMixin', 'CopyBudgetStartMixin',
    'register']


def register():
    Pool.register(
        account.BudgetContext,
        account.Budget,
        account.BudgetLine,
        account.BudgetLinePeriod,
        account.CopyBudgetStart,
        account.CreatePeriodsStart,
        module='account_budget', type_='model')
    Pool.register(
        account.CopyBudget,
        account.CreatePeriods,
        module='account_budget', type_='wizard')
