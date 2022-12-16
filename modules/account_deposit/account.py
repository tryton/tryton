# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['AccountTemplate', 'Account']
__metaclass__ = PoolMeta


class AccountTemplate:
    __name__ = 'account.account.template'

    @classmethod
    def __setup__(cls):
        super(AccountTemplate, cls).__setup__()
        cls.kind.selection.append(('deposit', 'Deposit'))


class Account:
    __name__ = 'account.account'

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls.kind.selection.append(('deposit', 'Deposit'))
