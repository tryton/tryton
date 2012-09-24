#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool, Id
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Carrier', 'WeightPriceList']
__metaclass__ = PoolMeta


class Carrier:
    __name__ = 'carrier'
    weight_uom = fields.Many2One('product.uom', 'Weight Uom',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        depends=['carrier_cost_method', 'weight_price_list'])
    weight_uom_digits = fields.Function(fields.Integer('Weight Uom Digits',
            on_change_with=['weight_uom']), 'on_change_with_weight_uom_digits')
    weight_currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        depends=['carrier_cost_method', 'weight_price_list'])
    weight_currency_digits = fields.Function(fields.Integer(
            'Weight Currency Digits', on_change_with=['weight_currency']),
        'on_change_with_weight_currency_digits')
    weight_price_list = fields.One2Many('carrier.weight_price_list', 'carrier',
        'Price List',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'readonly': ~(Eval('weight_uom', 0) & Eval('weight_currency', 0)),
            },
        depends=['carrier_cost_method', 'weight_uom', 'weight_currency'])

    @classmethod
    def __setup__(cls):
        super(Carrier, cls).__setup__()
        selection = ('weight', 'Weight')
        if selection not in cls.carrier_cost_method.selection:
            cls.carrier_cost_method.selection.append(selection)

    @staticmethod
    def default_weight_uom_digits():
        return 2

    @staticmethod
    def default_weight_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.digits
        return 2

    def on_change_with_weight_uom_digits(self, name=None):
        if self.weight_uom:
            return self.weight_uom.digits
        return 2

    def on_change_with_weight_currency_digits(self, name=None):
        if self.weight_currency:
            return self.weight_currency.digits
        return 2

    def compute_weight_price(self, weight):
        "Compute price based on weight"
        for line in reversed(self.weight_price_list):
            if line.weight < weight:
                return line.price
        return Decimal(0)

    def get_sale_price(self):
        price, currency_id = super(Carrier, self).get_sale_price()
        if self.carrier_cost_method == 'weight':
            weight_price = Decimal(0)
            for weight in Transaction().context.get('weights', []):
                weight_price += self.compute_weight_price(weight)
            return weight_price, self.weight_currency.id
        return price, currency_id

    def get_purchase_price(self):
        price, currency_id = super(Carrier, self).get_purchase_price()
        if self.carrier_cost_method == 'weight':
            weight_price = Decimal(0)
            for weight in Transaction().context.get('weights', []):
                weight_price += self.compute_weight_price(weight)
            return weight_price, self.weight_currency.id
        return price, currency_id


class WeightPriceList(ModelSQL, ModelView):
    'Carrier Weight Price List'
    __name__ = 'carrier.weight_price_list'
    carrier = fields.Many2One('carrier', 'Carrier', required=True, select=True)
    weight = fields.Float('Weight',
        digits=(16, Eval('_parent_carrier.weight_uom_digits', 2)))
    price = fields.Numeric('Price',
        digits=(16, Eval('_parent_carrier.weight_currency_digits', 2)))

    @classmethod
    def __setup__(cls):
        super(WeightPriceList, cls).__setup__()
        cls._order.insert(0, ('weight', 'ASC'))
