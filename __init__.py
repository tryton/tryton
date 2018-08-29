# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import sale
from . import stock

__all__ = ['register']


def register():
    Pool.register(
        sale.SubscriptionServiceStockLot,
        sale.SubscriptionService,
        sale.Subscription,
        sale.SubscriptionLine,
        stock.Lot,
        module='sale_subscription_asset', type_='model')
