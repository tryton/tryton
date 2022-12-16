# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import partial
from itertools import groupby

from trytond.pool import PoolMeta
from trytond.tools import sortable_values

from .common import parcel_weight


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return ()

    def _get_carrier_context(self):
        context = super(Sale, self)._get_carrier_context()

        if self.carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights

        lines = [l for l in self.lines or [] if l.quantity and l.quantity > 0]
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=sortable_values(keyfunc))

        for key, parcel in groupby(lines, key=keyfunc):
            weights.append(parcel_weight(
                    parcel, self.carrier.weight_uom, 'unit'))
        return context
