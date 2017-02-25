# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import invoice

__all__ = ['register']


def register():
    Pool.register(
        invoice.Invoice,
        invoice.InvoiceCorrectStart,
        module='account_invoice_correction', type_='model')
    Pool.register(
        invoice.InvoiceCorrect,
        module='account_invoice_correction', type_='wizard')
