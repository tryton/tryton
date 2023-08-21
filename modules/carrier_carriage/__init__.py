# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, incoterm, sale, stock

__all__ = ['register']


def register():
    Pool.register(
        stock.Carriage,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        module='carrier_carriage', type_='model')
    Pool.register(
        sale.Sale,
        sale.Line,
        sale.Carriage,
        stock.ShipmentCostSale,
        stock.Carriage_Sale,
        account.InvoiceLine,
        module='carrier_carriage', type_='model',
        depends=['sale_shipment_cost'])
    Pool.register(
        stock.Carriage_Purchase,
        stock.ShipmentIn,
        module='carrier_carriage', type_='model',
        depends=['purchase_shipment_cost'])
    Pool.register(
        incoterm.Incoterm,
        module='carrier_carriage', type_='model',
        depends=['incoterm'])
