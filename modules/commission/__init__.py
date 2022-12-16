# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    account, commission, commission_reporting, invoice, ir, party, product,
    sale)


def register():
    Pool.register(
        commission.Plan,
        commission.PlanLines,
        commission.Agent,
        commission.AgentSelection,
        commission.Commission,
        commission.CreateInvoiceAsk,
        commission_reporting.Agent,
        commission_reporting.AgentTimeseries,
        commission_reporting.Context,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.CreditInvoiceStart,
        product.Template,
        product.Template_Agent,
        product.Product,
        account.Journal,
        party.Party,
        ir.EmailTemplate,
        module='commission', type_='model')
    Pool.register(
        sale.Sale,
        sale.Line,
        module='commission', type_='model',
        depends=['sale'])
    Pool.register(
        commission.CreateInvoice,
        invoice.CreditInvoice,
        party.Replace,
        party.Erase,
        module='commission', type_='wizard')
