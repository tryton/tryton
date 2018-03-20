# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import carrier
from . import stock
from . import sale


def register():
    Pool.register(
        carrier.Carrier,
        module='carrier_percentage', type_='model')
    Pool.register(
        stock.ShipmentIn,
        module='carrier_percentage', type_='model',
        depends=['purchase_shipment_cost'])
    Pool.register(
        stock.ShipmentOut,
        sale.Sale,
        module='carrier_percentage', type_='model',
        depends=['sale_shipment_cost'])
