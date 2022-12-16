# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import tree, fields


class PriceList(tree(), metaclass=PoolMeta):
    __name__ = 'product.price_list'

    parent = fields.Many2One('product.price_list', "Parent")

    def get_context_formula(self, party, product, unit_price, quantity, uom,
            pattern=None):
        context = super(PriceList, self).get_context_formula(
            party, product, unit_price, quantity, uom, pattern=pattern)
        if self.parent:
            parent_unit_price = self.parent.compute(
                party, product, unit_price, quantity, uom, pattern=pattern)
            context['names']['parent_unit_price'] = parent_unit_price
        return context


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.formula.help += (
            '\n- parent_unit_price: the unit_price from the parent')
