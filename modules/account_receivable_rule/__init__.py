# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, ir
from .account import AccountRuleAbstract, AccountRuleAccountAbstract

__all__ = ['register', 'AccountRuleAbstract', 'AccountRuleAccountAbstract']


def register():
    Pool.register(
        ir.Cron,
        account.Account,
        account.Move,
        account.AccountReceivableRule,
        account.AccountReceivableRuleAccount,
        module='account_receivable_rule', type_='model')
    Pool.register(
        account.AccountReceivableRule_Dunning,
        module='account_receivable_rule', type_='model',
        depends=['account_dunning'])
    Pool.register(
        account.Statement,
        module='account_receivable_rule', type_='model',
        depends=['account_statement'])
