# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If


class ExciseTax(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.excise.tax'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.quantity.selection.append(
            ('ethanol_volume', "Alcohol Volume"))
        cls.uom.domain = [If(
                Eval('quantity') == 'ethanol_volume',
                [('category', '=', Id('product', 'uom_cat_volume'))],
                cls.uom.domain)]

    def convert_quantity(self, product, quantity):
        pool = Pool()
        UoM = pool.get('product.uom')

        converted = super().convert_quantity(product, quantity)
        if self.quantity == 'ethanol_volume':
            ethanol_by_volume = product.ethanol_by_volume_used
            if ethanol_by_volume is not None:
                if product.default_uom.category == self.uom.category:
                    quantity = quantity * ethanol_by_volume
                    converted = UoM.compute_qty(
                        product.default_uom, quantity, self.uom)
                elif product.volume is not None:
                    quantity = quantity * product.volume * ethanol_by_volume
                    converted = UoM.compute_qty(
                        product.volume_uom, quantity, self.uom)
        return converted


class ExciseTaxRate(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.excise.tax.rate'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.formula.help += ("\n"
            "-ethanol_by_volume: the percentage of alcohol by volume")

    def _compute_context(self, product, quantity):
        context = super()._compute_context(product, quantity)
        ethanol_by_volume = 0
        if product:
            ethanol_by_volume = product.ethanol_by_volume_used or 0
        ethanol_by_volume = Decimal(str(ethanol_by_volume))
        context['names'] = context['names'].copy()
        context['names']['ethanol_by_volume'] = ethanol_by_volume
        return context
