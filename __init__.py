# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import invoice


def register():
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceLine,
        module='account_invoice_line_standalone', type_='model')
