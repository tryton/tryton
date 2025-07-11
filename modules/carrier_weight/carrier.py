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
    weight_uom = fields.Many2One(
        'product.uom', "Weight UoM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        help="The Unit of Measure of weight criteria for the price list.")
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
        help="Add price per weight to the carrier service.\n"
        "The first line for which the weight is greater is used.\n"
        "The line with weight of 0 is used as default price.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        selection = ('weight', 'Weight')
        if selection not in cls.carrier_cost_method.selection:
            cls.carrier_cost_method.selection.append(selection)

    def compute_weight_price(self, weight):
        "Compute price based on weight"
        line = None
        for line in reversed(self.weight_price_list):
            if line.weight < weight:
                return line.price
        else:
            if line and not line.weight and not weight:
                return line.price
        return Decimal(0)

    def _get_weight_price(self):
        weights = Transaction().context.get('weights', [])
        if weights:
            weight_price = sum(
                self.compute_weight_price(w) for w in weights)
        else:
            weight_price = self.compute_weight_price(0)
        return weight_price, self.weight_currency.id

    def get_sale_price(self):
        price, currency_id = super().get_sale_price()
        if self.carrier_cost_method == 'weight':
            price, currency_id = self._get_weight_price()
        return price, currency_id

    def get_purchase_price(self):
        price, currency_id = super().get_purchase_price()
        if self.carrier_cost_method == 'weight':
            price, currency_id = self._get_weight_price()
        return price, currency_id


class WeightPriceList(ModelSQL, ModelView):
    __name__ = 'carrier.weight_price_list'
    carrier = fields.Many2One(
        'carrier', "Carrier", required=True,
        help="The carrier that the price list belongs to.")
    weight = fields.Float(
        "Weight", digits='weight_uom',
        domain=[
            ('weight', '>=', 0),
            ],
        depends={'carrier'},
        help="The lower limit for the price.")
    price = Monetary(
        "Price", currency='currency', digits='currency',
        help="The price of the carrier service.")

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')
    weight_uom = fields.Function(fields.Many2One(
            'product.uom', "Weight UoM",
            help="The Unit of Measure of the weight."),
        'on_change_with_weight_uom')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('weight', 'ASC'))

    @fields.depends('carrier', '_parent_carrier.weight_currency')
    def on_change_with_currency(self, name=None):
        return self.carrier.weight_currency if self.carrier else None

    @fields.depends('carrier', '_parent_carrier.weight_uom')
    def on_change_with_weight_uom(self, name=None):
        return self.carrier.weight_uom if self.carrier else None
