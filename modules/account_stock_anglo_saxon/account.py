# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['FiscalYear']


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls.account_stock_method.selection.append(
            ('anglo_saxon', 'Anglo-Saxon'))
