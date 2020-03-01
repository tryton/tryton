# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


def process_opportunity(func):
    @wraps(func)
    def wrapper(cls, sales):
        pool = Pool()
        Opportunity = pool.get('sale.opportunity')
        with Transaction().set_context(_check_access=False):
            opportunities = [s.origin for s in cls.browse(sales)
                if isinstance(s.origin, Opportunity)]
        func(cls, sales)
        with Transaction().set_context(_check_access=False):
            Opportunity.process(opportunities)
    return wrapper


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def _get_origin(cls):
        return super(Sale, cls)._get_origin() + ['sale.opportunity']

    @classmethod
    @process_opportunity
    def delete(cls, sales):
        super(Sale, cls).delete(sales)

    @classmethod
    @process_opportunity
    def cancel(cls, sales):
        super(Sale, cls).cancel(sales)

    @classmethod
    @process_opportunity
    def quote(cls, sales):
        super(Sale, cls).quote(sales)

    @classmethod
    @process_opportunity
    def confirm(cls, sales):
        super(Sale, cls).confirm(sales)

    @classmethod
    @process_opportunity
    def proceed(cls, sales):
        super(Sale, cls).proceed(sales)

    @classmethod
    @process_opportunity
    def do(cls, sales):
        super(Sale, cls).do(sales)
