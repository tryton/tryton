# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from stock import *
from carrier import *


def register():
    Pool.register(
        ShipmentIn,
        Move,
        Carrier,
        module='purchase_shipment_cost', type_='model')
