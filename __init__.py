# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import stock


def register():
    Pool.register(
        stock.Configuration,
        stock.ConfigurationSequence,
        stock.Type,
        stock.Package,
        stock.Move,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        module='stock_package', type_='model')
    Pool.register(
        stock.PackageLabel,
        module='stock_package', type_='report')
