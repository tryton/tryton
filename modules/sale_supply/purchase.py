# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


class Request(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    sale_lines = fields.One2Many(
        'sale.line', 'purchase_request', "Sale Lines", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'sale.sale'}

    @classmethod
    def delete(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        with Transaction().set_context(_check_access=False):
            reqs = cls.browse(requests)
            sales = set(r.origin for r in reqs if isinstance(r.origin, Sale))
            sale_lines = [l for r in reqs for l in r.sale_lines]
            if sale_lines:
                SaleLine.write(sale_lines, {
                        'purchase_request': None,
                        })

        super().delete(requests)

        if sales:
            Sale.__queue__.process(sales)


def process_sale_supply(func):
    @wraps(func)
    def wrapper(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        Sale = pool.get('sale.sale')

        sales = set()
        with Transaction().set_context(_check_access=False):
            for sub_purchases in grouped_slice(purchases):
                ids = [x.id for x in sub_purchases]
                requests = Request.search([
                        ('purchase_line.purchase.id', 'in', ids),
                        ('origin', 'like', 'sale.sale,%'),
                        ])
                sales.update(r.origin.id for r in requests)
        func(cls, purchases)
        if sales:
            Sale.__queue__.process(sales)
    return wrapper


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    @ModelView.button
    @process_sale_supply
    def process(cls, purchases):
        super(Purchase, cls).process(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @process_sale_supply
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)


class HandlePurchaseCancellationException(metaclass=PoolMeta):
    __name__ = 'purchase.request.handle.purchase.cancellation'

    def transition_cancel_request(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        Move = pool.get('stock.move')

        next_state = super(HandlePurchaseCancellationException,
            self).transition_cancel_request()
        moves = []
        for sub_ids in grouped_slice(list(map(int, self.records))):
            sale_lines = SaleLine.search([
                    ('purchase_request', 'in', sub_ids),
                    ])
            moves += [m for line in sale_lines for m in line.moves]
        if moves:
            Move.cancel(moves)
        return next_state
