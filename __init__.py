#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .purchase import *
from .stock import *
from .product import *


def register():
    Pool.register(
        Sale,
        SaleLine,
        PurchaseRequest,
        Purchase,
        ShipmentIn,
        Template,
        module='sale_supply', type_='model')
