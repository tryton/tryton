#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import Model
from trytond.pool import Pool


class Sale(Model):
    _name = 'sale.sale'

    def _get_carrier_context(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')

        context = super(Sale, self)._get_carrier_context(values)

        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'percentage':
            return context
        if not values.get('currency'):
            return context
        context = context.copy()
        amount = 0
        for line in values.get('lines') or []:
            if (line.get('unit_price') and line.get('quantity')
                    and not line.get('shipment_cost')):
                amount += (line['unit_price']
                    * Decimal(str(line['quantity'] or 0)))
        context['amount'] = amount
        context['currency'] = values['currency']
        return context

Sale()
