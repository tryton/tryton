# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta


class ShipmentCost(metaclass=PoolMeta):
    __name__ = 'account.shipment_cost'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.allocation_method.selection.append(('weight', "By Weight"))

    def allocate_cost_by_weight(self):
        self.factors = self._get_weight_factors()
        self._allocate_cost(self.factors)

    def unallocate_cost_by_weight(self):
        factors = self.factors or self._get_weight_factors()
        self._allocate_cost(factors, sign=-1)

    def _get_weight_factors(self):
        "Return the factor for each shipment based on weight"
        shipments = self.all_shipments
        sum_weight = sum(Decimal(s.weight or 0) for s in shipments)
        length = Decimal(len(shipments))
        factors = {}
        for shipment in shipments:
            if not sum_weight:
                factors[str(shipment.id)] = 1 / length
            else:
                factors[str(shipment.id)] = (
                    Decimal(shipment.weight or 0) / sum_weight)
        return factors
