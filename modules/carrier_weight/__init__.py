# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import carrier
from . import stock
from . import sale


def register():
    Pool.register(
        carrier.Carrier,
        carrier.WeightPriceList,
        module='carrier_weight', type_='model')
    Pool.register(
        stock.ShipmentIn,
        module='carrier_weight', type_='model',
        depends=['purchase_shipment_cost'])
    Pool.register(
        stock.ShipmentOut,
        sale.Sale,
        module='carrier_weight', type_='model',
        depends=['sale_shipment_cost'])
