#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import groupby
from functools import partial

from trytond.pool import Pool, PoolMeta

__all__ = ['ShipmentIn', 'ShipmentOut']
__metaclass__ = PoolMeta


class ShipmentIn:
    __name__ = 'stock.shipment.in'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return None

    def _get_carrier_context(self):
        Uom = Pool().get('product.uom')

        context = super(ShipmentIn, self)._get_carrier_context()
        if not self.carrier:
            return context
        if self.carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights

        lines = self.incoming_moves or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=keyfunc)

        for key, parcel in groupby(lines, key=keyfunc):
            weight = 0
            for line in parcel:
                if line.product and line.quantity and line.uom:
                    quantity = Uom.compute_qty(line.uom, line.quantity,
                        line.product.default_uom, round=False)
                    weight += Uom.compute_qty(line.product.weight_uom,
                        line.product.weight * quantity,
                        self.carrier.weight_uom, round=False)
            weights.append(weight)
        return context


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return None

    def _get_carrier_context(self):
        Uom = Pool().get('product.uom')

        context = super(ShipmentOut, self)._get_carrier_context()
        if not self.carrier:
            return context
        if self.carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights

        lines = self.inventory_moves or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=keyfunc)

        for key, parcel in groupby(lines, key=keyfunc):
            weight = 0
            for line in parcel:
                if line.product and line.quantity and line.uom:
                    quantity = Uom.compute_qty(line.uom, line.quantity,
                        line.product.default_uom, round=False)
                    weight += Uom.compute_qty(line.product.weight_uom,
                        line.product.weight * quantity,
                        self.carrier.weight_uom, round=False)
            weights.append(weight)
        return context
