# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from functools import wraps

from trytond.i18n import gettext
from trytond.model import Model, ModelView, Workflow
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
    @Workflow.transition('cancelled')
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
            if (production.state == 'cancelled'
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
        super().done(productions)

        for production in productions:
            production.assign_supplied()

    def assign_supplied(self, grouping=('product',), filter_=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        if isinstance(self.origin, SaleLine):
            sale_line = self.origin
        else:
            return

        def filter_func(move):
            if filter_ is None:
                return True
            for fieldname, values in filter_:
                value = getattr(move, fieldname)
                if isinstance(value, Model):
                    value = value.id
                if value not in values:
                    return False

        def get_key(move):
            key = (move.to_location.id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key

        pbl = defaultdict(lambda: defaultdict(int))
        for move in filter(filter_func, self.outputs):
            pbl[move.product][get_key(move)] += move.internal_quantity
        sale_line.assign_supplied(pbl[sale_line.product], grouping=grouping)
