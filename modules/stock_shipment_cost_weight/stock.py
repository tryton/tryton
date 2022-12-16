# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.pool import Pool, PoolMeta


class ShipmentCostMixinWeight:
    __slots__ = ()

    def _get_allocation_shipment_cost_factors_by_weight(self):
        pool = Pool()
        Move = pool.get('stock.move')
        if getattr(Move, 'internal_weight', None):
            sum_weight = Decimal(0)
            weights = {}
            for move in self.shipment_cost_moves:
                weight = Decimal(str(move.internal_weight or 0))
                weights[move.id] = weight
                sum_weight += weight

            if sum_weight:
                factors = {}
                for move in self.shipment_cost_moves:
                    factors[move.id] = weights[move.id] / sum_weight
                return factors
        return self._get_allocation_shipment_cost_factors_by_cost()


class ShipmentOut(ShipmentCostMixinWeight, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentOutReturn(
        ShipmentCostMixinWeight, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
