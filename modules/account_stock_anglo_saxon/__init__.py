#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .product import *
from .stock import *
from .invoice import *


def register():
    Pool.register(
        Category,
        Template,
        Move,
        InvoiceLine,
        module='account_stock_anglo_saxon', type_='model')
