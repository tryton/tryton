# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import party
from . import product
from . import purchase

__all__ = ['register']


def register():
    Pool.register(
        party.Party,
        party.PartyPurchasePriceList,
        product.Product,
        product.PriceList,
        purchase.Purchase,
        purchase.Line,
        module='purchase_price_list', type_='model')
