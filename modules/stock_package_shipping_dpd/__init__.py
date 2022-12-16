# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from .carrier import *
from .stock import *


def register():
    Pool.register(
        CredentialDPD,
        Carrier,
        ShipmentOut,
        module='stock_package_shipping_dpd', type_='model')
    Pool.register(
        CreateShipping,
        CreateDPDShipping,
        module='stock_package_shipping_dpd', type_='wizard')
