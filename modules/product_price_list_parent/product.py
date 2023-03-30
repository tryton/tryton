# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields, tree
from trytond.modules.product_price_list.price_list import Null
from trytond.pool import PoolMeta


class PriceList(tree(), metaclass=PoolMeta):
    __name__ = 'product.price_list'

    parent = fields.Many2One('product.price_list', "Parent")

    def get_context_formula(self, product, quantity, uom, pattern=None):
        context = super().get_context_formula(
            product, quantity, uom, pattern=pattern)
        if self.parent:
            parent_unit_price = self.parent.compute(
                product, quantity, uom, pattern=pattern)
            if parent_unit_price is None:
                parent_unit_price = Null()
            context['names']['parent_unit_price'] = parent_unit_price
        return context


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.formula.help += (
            '\n- parent_unit_price: the unit_price from the parent')
