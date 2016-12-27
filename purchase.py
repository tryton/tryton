# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Purchase', 'PurchaseLine']


class Purchase:
    __name__ = 'purchase.purchase'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'delete_purchase_request': ('You can not delete the purchase'
                    ' "%(purchase)s" because it is linked to at least one'
                    ' purchase request.'),
                })

    @classmethod
    def delete(cls, purchases):
        cls.check_delete_purchase_request(purchases)
        super(Purchase, cls).delete(purchases)

    def check_delete_purchase_request(cls, purchases):
        with Transaction().set_context(_check_access=False):
            purchases = cls.browse(purchases)
        for purchase in purchases:
            for line in purchase.lines:
                if line.requests:
                    cls.raise_user_error('delete_purchase_request', {
                            'purchase': purchase.rec_name,
                            })


class PurchaseLine:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.line'

    requests = fields.One2Many(
        'purchase.request', 'purchase_line', "Requests", readonly=True,
        states={
            'invisible': ~Eval('requests'),
            })
