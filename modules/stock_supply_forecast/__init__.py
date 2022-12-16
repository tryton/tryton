# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase_request


def register():
    Pool.register(
        purchase_request.Request,
        module='stock_supply_forecast', type_='model')
