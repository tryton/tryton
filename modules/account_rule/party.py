# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @property
    def account_payable_used(self):
        pool = Pool()
        AccountRule = pool.get('account.account.rule')
        account = super().account_payable_used
        with Transaction().set_context(account_type='payable'):
            account = AccountRule.apply(account)
        return account

    @property
    def account_receivable_used(self):
        pool = Pool()
        AccountRule = pool.get('account.account.rule')
        account = super().account_receivable_used
        with Transaction().set_context(account_type='receivable'):
            account = AccountRule.apply(account)
        return account
