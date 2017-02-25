# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

__all__ = ['PurchaseRequest', 'Purchase',
    'HandlePurchaseCancellationException']


class PurchaseRequest:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.request'

    sale_lines = fields.One2Many(
        'sale.line', 'purchase_request', "Sale Lines", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super(PurchaseRequest, cls)._get_origin() | {'sale.sale'}

    @classmethod
    def delete(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        with Transaction().set_context(_check_access=False):
            reqs = cls.browse(requests)
            sale_ids = list(set(r.origin.id for r in reqs
                    if isinstance(r.origin, Sale)))
            sale_lines = [l for r in reqs for l in r.sale_lines]
            if sale_lines:
                SaleLine.write(sale_lines, {
                        'purchase_request': None,
                        })

        super(PurchaseRequest, cls).delete(requests)

        if sale_ids:
            with Transaction().set_context(_check_access=False):
                Sale.process(Sale.browse(sale_ids))


class Purchase:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.purchase'

    @classmethod
    def _sale_supply_process(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        Sale = pool.get('sale.sale')

        requests = []
        for sub_purchases in grouped_slice(purchases):
            requests.append(Request.search([
                        ('purchase_line.purchase.id', 'in',
                            [x.id for x in sub_purchases]),
                        ('origin', 'like', 'sale.sale,%'),
                        ]))
        requests = list(chain(*requests))

        if requests:
            sale_ids = list(set(req.origin.id for req in requests))
            Sale.process(Sale.browse(sale_ids))

    @classmethod
    @ModelView.button
    def process(cls, purchases):
        super(Purchase, cls).process(purchases)
        cls._sale_supply_process(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)
        cls._sale_supply_process(purchases)


class HandlePurchaseCancellationException:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.request.handle.purchase.cancellation'

    def transition_cancel_request(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        Move = pool.get('stock.move')

        next_state = super(HandlePurchaseCancellationException,
            self).transition_cancel_request()
        moves = []
        for sub_ids in grouped_slice(Transaction().context['active_ids']):
            sale_lines = SaleLine.search([
                    ('purchase_request', 'in', sub_ids),
                    ])
            moves += [m for line in sale_lines for m in line.moves]
        if moves:
            Move.cancel(moves)
        return next_state
