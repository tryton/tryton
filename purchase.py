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
        SaleLine = pool.get('sale.line')
        cursor = Transaction().cursor

        sale_ids = list(set(r.origin.id for r in requests
                if isinstance(r.origin, Sale)))

        with Transaction().set_user(0, set_context=True):
            sale_lines = []
            for i in range(0, len(requests), cursor.IN_MAX):
                sub_requests = requests[i:i + cursor.IN_MAX]
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
            with Transaction().set_user(0, set_context=True):
                Sale.process(Sale.browse(sale_ids))


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
            sale_ids = list(set(req.origin.id for req in requests))
            with Transaction().set_user(0, set_context=True):
                Sale.process(Sale.browse(sale_ids))

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
