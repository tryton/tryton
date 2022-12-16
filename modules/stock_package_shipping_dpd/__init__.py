# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import carrier, stock


def register():
    Pool.register(
        carrier.CredentialDPD,
        carrier.Carrier,
        stock.Package,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        module='stock_package_shipping_dpd', type_='model')
    Pool.register(
        stock.CreateShipping,
        stock.CreateDPDShipping,
        module='stock_package_shipping_dpd', type_='wizard')
