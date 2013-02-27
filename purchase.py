#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain

from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['PurchaseRequest', 'Purchase']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def origin_get(cls):
        Model = Pool().get('ir.model')
        result = super(PurchaseRequest, cls).origin_get()
        model, = Model.search([
                ('model', '=', 'sale.sale'),
                ])
        result.append([model.model, model.name])
        return result

    @classmethod
    def delete(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')

        sales = [r.origin for r in requests if isinstance(r, Sale)]

        super(PurchaseRequest, cls).delete(requests)

        if sales:
            Sale.process(sales)


class Purchase:
    __name__ = 'purchase.purchase'

    @classmethod
    def _sale_supply_process(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        Sale = pool.get('sale.sale')
        cursor = Transaction().cursor

        requests = []
        for i in range(0, len(purchases), cursor.IN_MAX):
            purchase_ids = [p.id for p in purchases[i:i + cursor.IN_MAX]]
            requests.append(Request.search([
                        ('purchase_line.purchase.id', 'in', purchase_ids),
                        ('origin', 'like', 'sale.sale,%'),
                        ]))
        requests = list(chain(*requests))

        if requests:
            Sale.process([req.origin for req in requests])

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        super(Purchase, cls).confirm(purchases)
        cls._sale_supply_process(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)
        cls._sale_supply_process(purchases)
