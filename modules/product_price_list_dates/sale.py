# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = ['Line']


class Line:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.product.context['date'] = Eval(
            '_parent_sale', {}).get('sale_date')

    def _get_context_sale_price(self):
        context = super(Line, self)._get_context_sale_price()
        if 'sale_date' in context:
            context.setdefault('date', context['sale_date'])
        return context
