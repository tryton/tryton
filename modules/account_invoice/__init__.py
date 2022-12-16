# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import payment_term
from . import invoice
from . import party
from . import account
from . import company


def register():
    Pool.register(
        payment_term.PaymentTerm,
        payment_term.PaymentTermLine,
        payment_term.PaymentTermLineRelativeDelta,
        payment_term.TestPaymentTermView,
        payment_term.TestPaymentTermViewResult,
        invoice.Invoice,
        invoice.InvoicePaymentLine,
        invoice.InvoiceLine,
        invoice.InvoiceLineTax,
        invoice.InvoiceTax,
        invoice.PayInvoiceStart,
        invoice.PayInvoiceAsk,
        invoice.CreditInvoiceStart,
        party.Address,
        party.ContactMechanism,
        party.Party,
        party.PartyPaymentTerm,
        account.InvoiceSequence,
        # Match pattern migration fallbacks to Fiscalyear values so Period
        # must be registered before Fiscalyear
        account.Period,
        account.FiscalYear,
        account.Move,
        account.MoveLine,
        account.Reconciliation,
        invoice.PaymentMethod,
        company.Company,
        module='account_invoice', type_='model')
    Pool.register(
        payment_term.TestPaymentTerm,
        invoice.PayInvoice,
        invoice.CreditInvoice,
        party.Replace,
        party.Erase,
        account.RenewFiscalYear,
        module='account_invoice', type_='wizard')
    Pool.register(
        invoice.InvoiceReport,
        module='account_invoice', type_='report')
