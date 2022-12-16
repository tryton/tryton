# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import stock
from . import invoice
from . import account


def register():
    Pool.register(
        product.Category,
        product.CategoryAccount,
        product.Template,
        product.Product,
        stock.Move,
        invoice.InvoiceLine,
        account.FiscalYear,
        module='account_stock_anglo_saxon', type_='model')
