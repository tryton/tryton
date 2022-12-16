# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .stock import *


def register():
    Pool.register(
        Configuration,
        Type,
        Package,
        Move,
        ShipmentOut,
        ShipmentInReturn,
        module='stock_package', type_='model')
    Pool.register(
        PackageLabel,
        module='stock_package', type_='report')
