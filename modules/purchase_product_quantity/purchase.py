# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class RequestCreatePurchase(metaclass=PoolMeta):
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def compute_quantity(cls, requests, line, purchase):
        quantity = super().compute_quantity(requests, line, purchase)
        if line.product_supplier:
            quantity = line.product_supplier.adapt_quantity(
                quantity, line.unit, round=False)
        return quantity
