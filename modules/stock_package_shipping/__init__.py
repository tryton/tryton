# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from .stock import *
from .carrier import *


def register():
    Pool.register(
        PackageType,
        Package,
        ShipmentOut,
        Carrier,
        module='stock_package_shipping', type_='model')
    Pool.register(
        CreateShipping,
        module='stock_package_shipping', type_='wizard')
