# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .payment_term import *
from .invoice import *
from . import party
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
        PayInvoiceStart,
        PayInvoiceAsk,
        CreditInvoiceStart,
        party.Address,
        party.ContactMechanism,
        party.Party,
        party.PartyPaymentTerm,
        InvoiceSequence,
        # Match pattern migration fallbacks to Fiscalyear values so Period
        # must be registered before Fiscalyear
        Period,
        FiscalYear,
        Move,
        MoveLine,
        Reconciliation,
        module='account_invoice', type_='model')
    Pool.register(
        TestPaymentTerm,
        PayInvoice,
        CreditInvoice,
        party.PartyReplace,
        party.PartyErase,
        RenewFiscalYear,
        module='account_invoice', type_='wizard')
    Pool.register(
        InvoiceReport,
        module='account_invoice', type_='report')
