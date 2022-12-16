# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .payment_term import *
from .invoice import *
from .party import *
from .account import *


def register():
    Pool.register(
        PaymentTerm,
        PaymentTermLine,
        PaymentTermLineRelativeDelta,
        TestPaymentTermView,
        TestPaymentTermViewResult,
        Invoice,
        InvoicePaymentLine,
        InvoiceLine,
        InvoiceLineTax,
        InvoiceTax,
        PrintInvoiceWarning,
        PayInvoiceStart,
        PayInvoiceAsk,
        CreditInvoiceStart,
        Address,
        Party,
        FiscalYear,
        Period,
        Move,
        Reconciliation,
        module='account_invoice', type_='model')
    Pool.register(
        TestPaymentTerm,
        PrintInvoice,
        PayInvoice,
        CreditInvoice,
        module='account_invoice', type_='wizard')
    Pool.register(
        InvoiceReport,
        module='account_invoice', type_='report')
