# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class _AccountUsed:
    __slots__ = ()

    @property
    def account_expense_used(self):
        with Transaction().set_context(account_type='expense'):
            return super().account_expense_used

    @property
    def account_revenue_used(self):
        with Transaction().set_context(account_type='revenue'):
            return super().account_revenue_used

    @property
    def account_stock_used(self):
        with Transaction().set_context(account_type='stock'):
            return super().account_stock_used

    @property
    def account_stock_in_used(self):
        with Transaction().set_context(account_type='stock'):
            return super().account_stock_in_used

    @property
    def account_stock_out_used(self):
        with Transaction().set_context(account_type='stock'):
            return super().account_stock_out_used

    @property
    def account_cogs_used(self):
        with Transaction().set_context(account_type='stock'):
            return super().account_cogs_used


class Category(_AccountUsed, metaclass=PoolMeta):
    __name__ = 'product.category'

    def get_account(self, name, **pattern):
        pool = Pool()
        AccountRule = pool.get('account.account.rule')
        account = super().get_account(name, **pattern)
        if not self.account_parent:
            with Transaction().set_context(self._context):
                account = AccountRule.apply(account)
        return account


class Template(_AccountUsed, metaclass=PoolMeta):
    __name__ = 'product.template'
