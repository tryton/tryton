# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, stock

__all__ = ['register']


def register():
    Pool.register(
        stock.Location,
        stock.LocationLeadTime,
        stock.Move,
        stock.ShipmentInternal,
        stock.Inventory,
        account.InvoiceLine,
        module='stock_consignment', type_='model')
    Pool.register(
        stock.OrderPoint,
        module='stock_consignment', type_='model',
        depends=['stock_supply'])
