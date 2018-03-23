# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
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
        commission.Commission,
        commission.CreateInvoiceAsk,
        invoice.Invoice,
        invoice.InvoiceLine,
        product.Template,
        product.Template_Agent,
        product.Product,
        module='commission', type_='model')
    Pool.register(
        sale.Sale,
        sale.SaleLine,
        module='commission', type_='model',
        depends=['sale'])
    Pool.register(
        commission.CreateInvoice,
        party.PartyReplace,
        party.PartyErase,
        module='commission', type_='wizard')
