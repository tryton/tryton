# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import commission
from . import invoice
from . import sale
from . import product
from . import party


def register():
    Pool.register(
        commission.Plan,
        commission.PlanLines,
        commission.Agent,
        commission.AgentSelection,
        commission.Commission,
        commission.CreateInvoiceAsk,
        invoice.Invoice,
        invoice.InvoiceLine,
        product.Template,
        product.Template_Agent,
        product.Product,
        account.Journal,
        party.Party,
        module='commission', type_='model')
    Pool.register(
        sale.Sale,
        sale.Line,
        module='commission', type_='model',
        depends=['sale'])
    Pool.register(
        commission.CreateInvoice,
        party.Replace,
        party.Erase,
        module='commission', type_='wizard')
