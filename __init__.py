# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .stock import *


def register():
    Pool.register(
        InvoiceLineStockMove,
        InvoiceLine,
        StockMove,
        module='account_invoice_stock', type_='model')
