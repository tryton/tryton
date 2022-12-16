# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'
    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'invisible': Eval('carrier_cost_method') != 'percentage',
            },
        depends=['carrier_cost_method'],
        help="The percentage applied on the amount to compute the cost.")

    @classmethod
    def __setup__(cls):
        super(Carrier, cls).__setup__()
        selection = ('percentage', 'Percentage')
        if selection not in cls.carrier_cost_method.selection:
            cls.carrier_cost_method.selection.append(selection)

    def compute_percentage(self, amount, currency_id):
        "Compute price based on a percentage of amount"
        Currency = Pool().get('currency.currency')

        price = amount * self.percentage / Decimal(100)
        if not currency_id:
            return price, currency_id
        currency = Currency(currency_id)
        return currency.round(price), currency_id

    def get_sale_price(self):
        price, currency_id = super(Carrier, self).get_sale_price()
        if self.carrier_cost_method == 'percentage':
            amount = Transaction().context.get('amount', Decimal(0))
            currency_id = Transaction().context.get('currency', currency_id)
            return self.compute_percentage(amount, currency_id)
        return price, currency_id

    def get_purchase_price(self):
        price, currency_id = super(Carrier, self).get_purchase_price()
        if self.carrier_cost_method == 'percentage':
            amount = Transaction().context.get('amount', Decimal(0))
            currency_id = Transaction().context.get('currency', currency_id)
            return self.compute_percentage(amount, currency_id)
        return price, currency_id
