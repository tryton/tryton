# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.product.context['date'] = Eval(
            '_parent_sale', {}).get('sale_date')

    @fields.depends('sale', '_parent_sale.sale_date')
    def _get_context_sale_price(self):
        context = super(Line, self)._get_context_sale_price()
        if self.sale:
            context.setdefault('date', self.sale.sale_date)
        return context
