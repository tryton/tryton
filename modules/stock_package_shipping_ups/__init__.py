# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from .carrier import *
from .stock import *


def register():
    Pool.register(
        PackageType,
        ShipmentOut,
        CredentialUPS,
        Carrier,
        module='stock_package_shipping_ups', type_='model')
    Pool.register(
        CreateShipping,
        CreateShippingUPS,
        module='stock_package_shipping_ups', type_='wizard')
