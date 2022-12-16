# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def get_product_secondary_uom_category(self, name):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        category = super().get_product_secondary_uom_category(name)
        if isinstance(self.origin, PurchaseLine):
            if self.origin.secondary_unit:
                category = self.origin.secondary_unit.category.id
        return category

    @property
    def secondary_uom_factor(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        factor = super().secondary_uom_factor
        if isinstance(self.origin, PurchaseLine):
            factor = self.origin.secondary_uom_factor
        return factor

    @property
    def secondary_uom_rate(self):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        factor = super().secondary_uom_rate
        if isinstance(self.origin, PurchaseLine):
            factor = self.origin.secondary_uom_rate
        return factor
