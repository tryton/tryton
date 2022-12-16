# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from functools import partial

from trytond.pool import PoolMeta

from .common import parcel_weight

__all__ = ['ShipmentIn', 'ShipmentOut']


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return ()

    def _get_carrier_context(self):
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
            weights.append(parcel_weight(parcel, self.carrier.weight_uom))
        return context


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return ()

    def _get_carrier_context(self):
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
            weights.append(parcel_weight(parcel, self.carrier.weight_uom))
        return context
