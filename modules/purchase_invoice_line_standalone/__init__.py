# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase


def register():
    Pool.register(
        purchase.Purchase,
        purchase.PurchaseIgnoredInvoiceLine,
        module='purchase_invoice_line_standalone', type_='model')
    Pool.register(
        purchase.HandleInvoiceException,
        module='purchase_invoice_line_standalone', type_='wizard')
