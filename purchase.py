# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain

from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

__all__ = ['PurchaseRequest', 'Purchase']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def _get_origin(cls):
        return super(PurchaseRequest, cls)._get_origin() | {'sale.sale'}

    @classmethod
    def delete(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        sale_ids = list(set(r.origin.id for r in requests
                if isinstance(r.origin, Sale)))

        with Transaction().set_context(_check_access=False):
            sale_lines = []
            for sub_requests in grouped_slice(requests):
                sale_lines.append(SaleLine.search([
                            ('purchase_request', 'in',
                                [r.id for r in sub_requests]),
                            ]))
            sale_lines = list(chain(*sale_lines))
            if sale_lines:
                SaleLine.write(sale_lines, {
                        'purchase_request': None,
                        })

        super(PurchaseRequest, cls).delete(requests)

        if sale_ids:
            with Transaction().set_context(_check_access=False):
                Sale.process(Sale.browse(sale_ids))


class Purchase:
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
