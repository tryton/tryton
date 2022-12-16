# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .party import *
from .payment_term import *
from .invoice import *


def register():
    Pool.register(
        Party,
        Address,
        PaymentTerm,
        PaymentTermLine,
        Invoice,
        module='account_invoice_history', type_='model')
