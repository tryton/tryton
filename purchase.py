# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Purchase', 'PurchaseLine']


def process_request(func):
    @wraps(func)
    def wrapper(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        func(cls, purchases)
        requests = [r for p in purchases for l in p.lines for r in l.requests]
        Request.update_state(requests)
    return wrapper


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._error_messages.update({
                'delete_purchase_request': ('You can not delete the purchase'
                    ' "%(purchase)s" because it is linked to at least one'
                    ' purchase request.'),
                'warehouse_request_purchase_mismatch': ('The warehouse'
                    ' "%(purchase_warehouse)s" of purchase "%(purchase)s"'
                    ' is different of the warehouse "%(request_warehouse)s"'
                    ' of the linked purchase request.'),
                })

    @classmethod
    def delete(cls, purchases):
        cls.check_delete_purchase_request(purchases)
        super(Purchase, cls).delete(purchases)

    @classmethod
    def check_delete_purchase_request(cls, purchases):
        with Transaction().set_context(_check_access=False):
            purchases = cls.browse(purchases)
        for purchase in purchases:
            for line in purchase.lines:
                if line.requests:
                    cls.raise_user_error('delete_purchase_request', {
                            'purchase': purchase.rec_name,
                            })

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        for purchase in purchases:
            purchase.check_request_warehouse()
        super(Purchase, cls).confirm(purchases)

    def check_request_warehouse(self):
        for line in self.lines:
            for request in line.requests:
                if request.warehouse != self.warehouse:
                    w_name = 'check_request_warehouse_%s_%s_%s' % (
                        self.id, self.warehouse.id, request.warehouse.id)
                    self.raise_user_warning(
                        w_name, 'warehouse_request_self_mismatch', {
                            'purchase': self.rec_name,
                            'purchase_warehouse': self.warehouse.rec_name,
                            'request_warehouse': request.warehouse.rec_name,
                            })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    @process_request
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)

    @classmethod
    @Workflow.transition('done')
    @process_request
    def do(cls, purchases):
        super(Purchase, cls).do(purchases)


class PurchaseLine(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    requests = fields.One2Many(
        'purchase.request', 'purchase_line', "Requests", readonly=True,
        states={
            'invisible': ~Eval('requests'),
            })

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        Request = pool.get('purchase.request')
        with Transaction().set_context(_check_access=False):
            requests = [r for l in cls.browse(lines) for r in l.requests]
        super(PurchaseLine, cls).delete(lines)
        with Transaction().set_context(_check_access=False):
            Request.update_state(requests)
