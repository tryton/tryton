# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock
from . import carrier


def register():
    Pool.register(
        stock.ShipmentIn,
        stock.Move,
        carrier.Carrier,
        module='purchase_shipment_cost', type_='model')
