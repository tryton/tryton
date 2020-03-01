# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale
from . import stock


def register():
    Pool.register(
        sale.Configuration,
        sale.ConfigurationSaleMethod,
        sale.Sale,
        sale.Line,
        stock.ShipmentOut,
        module='sale_shipment_cost', type_='model')
    Pool.register(
        sale.Promotion,
        module='sale_shipment_cost', type_='model',
        depends=['sale_promotion'])
    Pool.register(
        sale.ReturnSale,
        module='sale_shipment_cost', type_='wizard')
