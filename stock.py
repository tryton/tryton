#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import izip

from trytond.model import Model
from trytond.pool import Pool
from trytond.transaction import Transaction


def _percentage_amount(lines, company):
    pool = Pool()
    move_obj = pool.get('stock.move')
    currency_obj = pool.get('currency.currency')

    amount = 0
    for line in lines or []:
        if line['id'] >= 0:
            move = move_obj.browse(line['id'])
        else:
            move = None
        if 'unit_price' in line:
            unit_price = line['unit_price']
        elif move:
            unit_price = move.unit_price
        elif hasattr(move_obj, 'default_unit_price'):
            unit_price = move_obj.default_unit_price()
        else:
            unit_price = Decimal('0')
        if 'currency' in line:
            currency_id = line['currency']
        elif move:
            currency_id = move.currency.id
        elif hasattr(move_obj, 'default_currency'):
            currency_id = move_obj.default_currency()
        else:
            currency_id = None
        if currency_id:
            unit_price = currency_obj.compute(currency_id, unit_price,
                company.currency.id, round=False)
        amount += unit_price * Decimal(str(line['quantity'] or 0))
    return amount


class ShipmentIn(Model):
    _name = 'stock.shipment.in'

    def _get_carrier_context(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        company_obj = pool.get('company.company')
        context = super(ShipmentIn, self)._get_carrier_context(values)
        if not values.get('carrier'):
            return context
        context = context.copy()
        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'percentage':
            return context
        company = company_obj.browse(Transaction().context['company'])
        context['amount'] = _percentage_amount(values['incoming_moves'],
            company)
        context['currency'] = company.currency.id
        return context

ShipmentIn()


class ShipmentOut(Model):
    _name = 'stock.shipment.out'

    def _get_carrier_context(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        company_obj = pool.get('company.company')

        context = super(ShipmentOut, self)._get_carrier_context(values)
        if not values.get('carrier'):
            return context
        context = context.copy()
        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'percentage':
            return context
        company = company_obj.browse(Transaction().context['company'])
        context['amount'] = _percentage_amount(values['inventory_moves'],
            company)
        context['currency'] = company.currency.id
        return context

    def get_carrier_context(self, shipment, values=None):
        if values is None:
            values = {}
        values = values.copy()
        inventory_moves = [{
                'id': m.id,
                'unit_price': m.unit_price,
                'currency': m.currency.id,
                'quantity': m.quantity,
                } for m in shipment.inventory_moves]
        values.setdefault('inventory_moves', inventory_moves)
        for new, old in izip(inventory_moves, values['inventory_moves']):
            old.update(new)
        return super(ShipmentOut, self).get_carrier_context(shipment,
            values=values)

ShipmentOut()
