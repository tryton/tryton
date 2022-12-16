# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account

__all__ = ['register']


def register():
    Pool.register(
        account.ShipmentCost,
        module='account_stock_shipment_cost_weight', type_='model')
