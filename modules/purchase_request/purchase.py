# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tools import grouped_slice
from trytond.pool import Pool, PoolMeta

__all__ = ['Purchase']


class Purchase:
    __name__ = 'purchase.purchase'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'delete_purchase_request': ('You can not delete the purchase'
                    ' "%(purchase)s" because it is linked to at least one'
                    ' purchase request."'),
                })

    @classmethod
    def delete(cls, purchases):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')

        purchase_lines = [pl.id
            for purchase in purchases for pl in purchase.lines]
        for sub_lines in grouped_slice(purchase_lines):
            requests = PurchaseRequest.search([
                    ('purchase_line', 'in', list(sub_lines)),
                    ],
                limit=1)
            if requests:
                purchase = requests[0].purchase
                cls.raise_user_error('delete_purchase_request', {
                        'purchase': purchase.rec_name,
                        })

        super(Purchase, cls).delete(purchases)
