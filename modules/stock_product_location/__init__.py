# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import location
from . import production


def register():
    Pool.register(
        product.Template,
        product.Product,
        location.ProductLocation,
        location.Move,
        location.ShipmentIn,
        location.ShipmentOutReturn,
        module='stock_product_location', type_='model')
    Pool.register(
        production.Production,
        module='stock_product_location', type_='model',
        depends=['production'])
