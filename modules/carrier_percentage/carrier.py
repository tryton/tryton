#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from decimal import Decimal
from trytond.model import Model, fields
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval


class Carrier(Model):
    _name = 'carrier'

    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'invisible': Eval('carrier_cost_method') != 'percentage',
            },
        depends=['carrier_cost_method'])

    def __init__(self):
        super(Carrier, self).__init__()
        self.carrier_cost_method = copy.copy(self.carrier_cost_method)
        self.carrier_cost_method.selection = \
            self.carrier_cost_method.selection[:]
        selection = ('percentage', 'Percentage')
        if selection not in self.carrier_cost_method.selection:
            self.carrier_cost_method.selection.append(selection)
        self._reset_columns()

    def compute_percentage(self, carrier, amount, currency_id):
        "Compute price based on a percentage of amount"
        currency_obj = Pool().get('currency.currency')

        price = amount * carrier.percentage / Decimal(100)
        if not currency_id:
            return price, currency_id
        currency = currency_obj.browse(currency_id)
        return currency_obj.round(currency, price), currency_id

    def get_sale_price(self, carrier):
        price, currency_id = super(Carrier, self).get_sale_price(carrier)
        if carrier.carrier_cost_method == 'percentage':
            amount = Transaction().context.get('amount', Decimal(0))
            currency_id = Transaction().context.get('currency', currency_id)
            return self.compute_percentage(carrier, amount, currency_id)
        return price, currency_id

    def get_purchase_price(self, carrier):
        price, currency_id = super(Carrier, self).get_purchase_price(carrier)
        if carrier.carrier_cost_method == 'percentage':
            amount = Transaction().context.get('amount', Decimal(0))
            currency_id = Transaction().context.get('currency', currency_id)
            return self.compute_percentage(carrier, amount, currency_id)
        return price, currency_id

Carrier()
