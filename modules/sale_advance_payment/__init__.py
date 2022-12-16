# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale
from . import account
from . import stock


def register():
    Pool.register(
        sale.AdvancePaymentTerm,
        sale.AdvancePaymentTermLine,
        sale.AdvancePaymentTermLineAccount,
        sale.AdvancePaymentCondition,
        sale.Sale,
        sale.SaleLine,
        account.Invoice,
        account.InvoiceLine,
        stock.ShipmentOut,
        module='sale_advance_payment', type_='model')
    Pool.register(
        sale.HandleInvoiceException,
        module='sale_advance_payment', type_='wizard')
