#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta

__all__ = ['Sale']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    def _get_carrier_context(self):
        context = super(Sale, self)._get_carrier_context()

        if self.carrier.carrier_cost_method != 'percentage':
            return context
        if not self.currency:
            return context
        context = context.copy()
        amount = 0
        for line in self.lines or []:
            if line.unit_price and line.quantity and not line.shipment_cost:
                amount += (line.unit_price
                    * Decimal(str(line.quantity or 0)))
        context['amount'] = amount
        context['currency'] = self.currency.id
        return context
