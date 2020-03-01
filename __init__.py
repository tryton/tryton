# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import commission
from . import invoice
from . import account


def register():
    Pool.register(
        commission.Agent,
        commission.Commission,
        invoice.Invoice,
        invoice.InvoiceLine,
        account.Move,
        module='commission_waiting', type_='model')
