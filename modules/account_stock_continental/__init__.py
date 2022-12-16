# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import product
from . import account


def register():
    Pool.register(
        stock.Move,
        product.Category,
        product.CategoryAccount,
        product.Template,
        product.Product,
        account.Configuration,
        account.ConfigurationStockJournal,
        account.FiscalYear,
        account.AccountMove,
        module='account_stock_continental', type_='model')
