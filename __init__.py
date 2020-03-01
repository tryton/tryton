# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import complaint
from . import sale
from . import account


def register():
    Pool.register(
        complaint.Type,
        complaint.Complaint,
        complaint.Action,
        complaint.Action_SaleLine,
        complaint.Action_InvoiceLine,
        sale.Configuration,
        sale.ConfigurationSequence,
        sale.Sale,
        account.InvoiceLine,
        module='sale_complaint', type_='model')
