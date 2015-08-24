# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

__all__ = ['LandedCost']


class LandedCost:
    __metaclass__ = PoolMeta
    __name__ = 'account.landed_cost'

    @classmethod
    def __setup__(cls):
        super(LandedCost, cls).__setup__()
        cls.allocation_method.selection.append(('weight', 'By Weight'))

    def allocate_cost_by_weight(self):
        self._allocate_cost(self._get_weight_factors())

    def _get_weight_factors(self):
        "Return the factor for each move based on weight"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        kg = Uom(ModelData.get_id('product', 'uom_kilogram'))
        moves = [m for s in self.shipments for m in s.incoming_moves
            if m.state != 'cancel']

        sum_weight = Decimal(0)
        weights = {}
        for move in moves:
            if not move.product.weight:
                weight = 0
            else:
                weight = Uom.compute_qty(
                    move.product.weight_uom,
                    move.product.weight * move.internal_quantity,
                    kg, round=False)
            weight = Decimal(str(weight))
            weights[move.id] = weight
            sum_weight += weight
        factors = {}
        length = Decimal(len(moves))
        for move in moves:
            if not sum_weight:
                factors[move.id] = 1 / length
            else:
                factors[move.id] = weights[move.id] / sum_weight
        return factors
