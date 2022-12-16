# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import carrier, stock

__all__ = ['register']


def register():
    Pool.register(
        carrier.CredentialMyGLS,
        carrier.Carrier,
        stock.Package,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        module='stock_package_shipping_mygls', type_='model')
    Pool.register(
        stock.ShipmentCreateShipping,
        stock.ShipmentCreateShippingMyGLS,
        module='stock_package_shipping_mygls', type_='wizard')
