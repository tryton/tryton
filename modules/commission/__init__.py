# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .commission import *
from .invoice import *
from .sale import *
from .product import *
from . import party


def register():
    Pool.register(
        Plan,
        PlanLines,
        Agent,
        Commission,
        CreateInvoiceAsk,
        Invoice,
        InvoiceLine,
        Sale,
        SaleLine,
        Template,
        Template_Agent,
        Product,
        module='commission', type_='model')
    Pool.register(
        CreateInvoice,
        party.PartyReplace,
        module='commission', type_='wizard')
