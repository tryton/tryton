# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import stock


def register():
    Pool.register(
        account.Invoice,
        account.InvoiceLineStockMove,
        account.InvoiceLine,
        stock.Move,
        stock.ShipmentOut,
        module='account_invoice_stock', type_='model')
