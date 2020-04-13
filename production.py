# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta, Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


def process_sale_supply(func):
    @wraps(func)
    def wrapper(cls, productions):
        pool = Pool()
        Sale = pool.get('sale.sale')

        sales = set()
        with Transaction().set_context(_check_access=False):
            for sub_productions in grouped_slice(productions):
                ids = [p.id for p in sub_productions]
                sales.update([s.id for s in Sale.search([
                                ('lines.productions', 'in', ids),
                                ])])
        func(cls, productions)
        if sales:
            Sale.__queue__.process(sales)
    return wrapper


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() | {'sale.line'}

    @classmethod
    @process_sale_supply
    def delete(cls, productions):
        super().delete(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    @process_sale_supply
    def cancel(cls, productions):
        super().cancel(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        for production in productions:
            if (production.state == 'cancel'
                    and isinstance(production.origin, SaleLine)):
                raise AccessError(
                    gettext('sale_supply_production'
                        '.msg_production_reset_draft',
                        production=production.rec_name))
        super().draft(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    @process_sale_supply
    def run(cls, productions):
        super().run(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @process_sale_supply
    def done(cls, productions):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        super().done(productions)

        for production in productions:
            pbl = defaultdict(lambda: defaultdict(int))
            for move in production.outputs:
                pbl[move.product][move.to_location] += move.internal_quantity
            if isinstance(production.origin, SaleLine):
                sale_line = production.origin
                sale_line.assign_supplied(pbl[sale_line.product])
