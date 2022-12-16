# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .commission import *
from .invoice import *
from .account import *


def register():
    Pool.register(
        Agent,
        Commission,
        Invoice,
        InvoiceLine,
        Move,
        module='commission_waiting', type_='model')
