# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction, without_check_access


class Request(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    sale_lines = fields.One2Many(
        'sale.line', 'purchase_request', "Sale Lines", readonly=True)

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'sale.sale'}

    @classmethod
    def update_state(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')
        transaction = Transaction()
        context = transaction.context

        super().update_state(requests)

        sales = {r.origin for r in requests if isinstance(r.origin, Sale)}
        if sales:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Sale.__queue__.process(Sale.browse(sales))

    @classmethod
    def copy(cls, requests, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('sale_lines')
        return super().copy(requests, default=default)

    @classmethod
    def delete(cls, requests):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        transaction = Transaction()
        context = transaction.context

        with without_check_access():
            reqs = cls.browse(requests)
            sales = set(r.origin for r in reqs if isinstance(r.origin, Sale))
            sale_lines = [l for r in reqs for l in r.sale_lines]
            if sale_lines:
                SaleLine.write(sale_lines, {
                        'purchase_request': None,
                        })

        super().delete(requests)

        if sales:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Sale.__queue__.process(sales)
