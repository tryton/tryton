# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import stock
from . import carrier


def register():
    Pool.register(
        stock.PackageType,
        stock.Package,
        stock.ShipmentOut,
        carrier.Carrier,
        module='stock_package_shipping', type_='model')
    Pool.register(
        stock.CreateShipping,
        module='stock_package_shipping', type_='wizard')
