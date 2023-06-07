# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.search_context['date'] = Eval(
            '_parent_purchase', {}).get('purchase_date')

    @fields.depends('purchase', '_parent_purchase.purchase_date')
    def _get_context_purchase_price(self):
        context = super()._get_context_purchase_price()
        if self.purchase:
            context.setdefault('date', self.purchase.purchase_date)
        return context
