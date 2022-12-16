# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Rule(metaclass=PoolMeta):
    __name__ = 'analytic_account.rule'

    product = fields.Many2One('product.product', "Product", ondelete='CASCADE')
    product_category = fields.Many2One(
        'product.category', "Product Category", ondelete='CASCADE')

    def match(self, pattern):
        if 'product_categories' in pattern:
            pattern = pattern.copy()
            categories = pattern.pop('product_categories')
            if (self.product_category is not None
                    and self.product_category.id not in categories):
                return False
        return super().match(pattern)
