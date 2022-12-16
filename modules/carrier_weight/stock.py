# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import partial
from itertools import groupby

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.tools import sortable_values

from .common import parcel_weight


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return ()

    @fields.depends('carrier')
    def _parcel_weight(self, parcel):
        if self.carrier:
            return parcel_weight(parcel, self.carrier.weight_uom)

    @fields.depends('carrier', 'incoming_moves',
        methods=['_group_parcel_key', '_parcel_weight'])
    def _get_carrier_context(self):
        context = super(ShipmentIn, self)._get_carrier_context()
        if not self.carrier:
            return context
        if self.carrier.carrier_cost_method != 'weight':
            return context
        weights = []
        context['weights'] = weights

        lines = self.incoming_moves or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=sortable_values(keyfunc))

        for key, parcel in groupby(lines, key=keyfunc):
            weights.append(self._parcel_weight(parcel))
        return context


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return ()

    @fields.depends('carrier')
    def _parcel_weight(self, parcel):
        if self.carrier:
            return parcel_weight(parcel, self.carrier.weight_uom)

    @fields.depends(
        'state', 'carrier', 'inventory_moves', 'outgoing_moves',
        'warehouse_storage', 'warehouse_output',
        methods=['_group_parcel_key', '_parcel_weight'])
    def _get_carrier_context(self):
        context = super(ShipmentOut, self)._get_carrier_context()
        if not self.carrier:
            return context
        if self.carrier.carrier_cost_method != 'weight':
            return context
        weights = []
        context['weights'] = weights

        if (self.state in {'draft', 'waiting', 'assigned'}
                and self.warehouse_storage != self.warehouse_output):
            lines = self.inventory_moves or []
        else:
            lines = self.outgoing_moves or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=sortable_values(keyfunc))

        for key, parcel in groupby(lines, key=keyfunc):
            weights.append(self._parcel_weight(parcel))
        return context
