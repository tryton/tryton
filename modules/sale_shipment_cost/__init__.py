# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .stock import *


def register():
    Pool.register(
        Configuration,
        Sale,
        SaleLine,
        ShipmentOut,
        module='sale_shipment_cost', type_='model')
