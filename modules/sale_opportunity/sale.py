# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import without_check_access


def process_opportunity(func):
    @wraps(func)
    def wrapper(cls, sales):
        pool = Pool()
        Opportunity = pool.get('sale.opportunity')
        with without_check_access():
            opportunities = Opportunity.browse(
                set(s.origin for s in cls.browse(sales)
                    if isinstance(s.origin, Opportunity)))
        result = func(cls, sales)
        with without_check_access():
            Opportunity.process(opportunities)
        return result
    return wrapper


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['sale.opportunity']

    @classmethod
    def check_modification(cls, mode, sales, values=None, external=False):
        pool = Pool()
        Opportunity = pool.get('sale.opportunity')

        super().check_modification(
            mode, sales, values=values, external=external)

        if mode == 'write' and 'origin' in values:
            origin = values['origin']
            if origin and not isinstance(origin, str):
                origin = '%s,%s' % tuple(origin)
            for sale in sales:
                if (isinstance(sale.origin, Opportunity)
                        and str(sale.origin) != origin):
                    raise AccessError(gettext(
                            'sale_opportunity'
                            '.msg_modify_origin_opportunity',
                            sale=sale.rec_name))

    @classmethod
    @process_opportunity
    def cancel(cls, sales):
        super().cancel(sales)

    @classmethod
    @process_opportunity
    def quote(cls, sales):
        super().quote(sales)

    @classmethod
    @process_opportunity
    def confirm(cls, sales):
        super().confirm(sales)

    @classmethod
    @process_opportunity
    def proceed(cls, sales):
        super().proceed(sales)

    @classmethod
    @process_opportunity
    def do(cls, sales):
        super().do(sales)
