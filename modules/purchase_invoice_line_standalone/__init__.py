#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .purchase import *
from .invoice import *


def register():
    Pool.register(
        Purchase,
        PurchaseInvoiceLine,
        PurchaseIgnoredInvoiceLine,
        InvoiceLine,
        module='purchase_invoice_line_standalone', type_='model')
    Pool.register(
        HandleInvoiceException,
        module='purchase_invoice_line_standalone', type_='wizard')
