# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval, Id
from trytond.transaction import Transaction


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'
    weight_uom = fields.Many2One('product.uom', 'Weight Uom',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        help="The unit of weight criteria of the price list.")
    weight_uom_digits = fields.Function(fields.Integer('Weight Uom Digits'),
        'on_change_with_weight_uom_digits')
    weight_currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        help="The currency of the price.")
    weight_price_list = fields.One2Many('carrier.weight_price_list', 'carrier',
        'Price List',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'readonly': ~(Eval('weight_uom', 0) & Eval('weight_currency', 0)),
            },
        help="Add price to the carrier service.")

    @classmethod
    def __setup__(cls):
        super(Carrier, cls).__setup__()
        selection = ('weight', 'Weight')
        if selection not in cls.carrier_cost_method.selection:
            cls.carrier_cost_method.selection.append(selection)

    @staticmethod
    def default_weight_uom_digits():
        return 2

    @fields.depends('weight_uom')
    def on_change_with_weight_uom_digits(self, name=None):
        if self.weight_uom:
            return self.weight_uom.digits
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
    carrier = fields.Many2One('carrier', 'Carrier', required=True, select=True,
        help="The carrier that the price list belongs to.")
    weight = fields.Float('Weight',
        digits=(16, Eval('_parent_carrier', {}).get('weight_uom_digits', 2)),
        depends={'carrier'},
        help="The lower limit for the price.")
    price = Monetary(
        "Price", currency='currency', digits='currency',
        help="The price of the carrier service.")

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super(WeightPriceList, cls).__setup__()
        cls._order.insert(0, ('weight', 'ASC'))

    @fields.depends('carrier', '_parent_carrier.weight_currency')
    def on_change_with_currency(self, name=None):
        if self.carrier and self.carrier.weight_currency:
            return self.carrier.weight_currency.id
