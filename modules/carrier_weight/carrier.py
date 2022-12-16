#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from decimal import Decimal

from trytond.model import Model, ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool, PYSON
from trytond.pool import Pool
from trytond.transaction import Transaction


class Id(PYSON):

    def __init__(self, module, fs_id):
        super(Id, self).__init__()
        self._module = module
        self._fs_id = fs_id

    def pyson(self):
        model_data_obj = Pool().get('ir.model.data')
        return model_data_obj.get_id(self._module, self._fs_id)

    def types(self):
        return set([int])


class Carrier(Model):
    _name = 'carrier'

    weight_uom = fields.Many2One('product.uom', 'Weight Uom',
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        depends=['carrier_cost_method', 'weight_price_list'])
    weight_uom_digits = fields.Function(fields.Integer('Weight Uom Digits',
            on_change_with=['weight_uom']), 'get_weight_uom_digits')
    weight_currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'required': Eval('carrier_cost_method') == 'weight',
            'readonly': Bool(Eval('weight_price_list', [])),
            },
        depends=['carrier_cost_method', 'weight_price_list'])
    weight_currency_digits = fields.Function(fields.Integer(
            'Weight Currency Digits', on_change_with=['weight_currency']),
        'get_weight_currency_digits')
    weight_price_list = fields.One2Many('carrier.weight_price_list', 'carrier',
        'Price List',
        states={
            'invisible': Eval('carrier_cost_method') != 'weight',
            'readonly': ~(Eval('weight_uom', 0) & Eval('weight_currency', 0)),
            },
        depends=['carrier_cost_method', 'weight_uom', 'weight_currency'])

    def __init__(self):
        super(Carrier, self).__init__()
        self.carrier_cost_method = copy.copy(self.carrier_cost_method)
        self.carrier_cost_method.selection = \
            self.carrier_cost_method.selection[:]
        selection = ('weight', 'Weight')
        if selection not in self.carrier_cost_method.selection:
            self.carrier_cost_method.selection.append(selection)
        self._reset_columns()

    def default_weight_uom_digits(self):
        return 2

    def default_weight_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return company_obj.browse(company).currency.digits
        return 2

    def on_change_with_weight_uom_digits(self, values):
        uom_obj = Pool().get('product.uom')
        if values.get('weight_uom'):
            uom = uom_obj.browse(values['weight_uom'])
            return uom.digits
        return 2

    def get_weight_uom_digits(self, ids, name):
        digits = {}
        for carrier in self.browse(ids):
            if carrier.weight_uom:
                digits[carrier.id] = carrier.weight_uom.digits
            else:
                digits[carrier.id] = 2
        return digits

    def on_change_with_weight_currency_digits(self, values):
        currency_obj = Pool().get('currency.currency')
        if values.get('weight_currency'):
            currency = currency_obj.browse(values['weight_currency'])
            return currency.digits
        return 2

    def get_weight_currency_digits(self, ids, name):
        digits = {}
        for carrier in self.browse(ids):
            if carrier.weight_currency:
                digits[carrier.id] = carrier.weight_currency.digits
            else:
                digits[carrier.id] = 2
        return digits

    def compute_weight_price(self, carrier, weight):
        "Compute price based on weight"
        for line in reversed(carrier.weight_price_list):
            if line.weight < weight:
                return line.price
        return Decimal(0)

    def get_sale_price(self, carrier):
        price, currency_id = super(Carrier, self).get_sale_price(carrier)
        if carrier.carrier_cost_method == 'weight':
            weight_price = Decimal(0)
            for weight in Transaction().context.get('weights', []):
                weight_price += self.compute_weight_price(carrier, weight)
            return weight_price, carrier.weight_currency.id
        return price, currency_id

    def get_purchase_price(self, carrier):
        price, currency_id = super(Carrier, self).get_purchase_price(carrier)
        if carrier.carrier_cost_method == 'weight':
            weight_price = Decimal(0)
            for weight in Transaction().context.get('weights', []):
                weight_price += self.compute_weight_price(carrier, weight)
            return weight_price, carrier.weight_currency.id
        return price, currency_id

Carrier()


class WeightPriceList(ModelSQL, ModelView):
    'Carrier Weight Price List'
    _name = 'carrier.weight_price_list'

    carrier = fields.Many2One('carrier', 'Carrier', required=True, select=True)
    weight = fields.Float('Weight',
        digits=(16, Eval('_parent_carrier.weight_uom_digits', 2)))
    price = fields.Numeric('Price',
        digits=(16, Eval('_parent_carrier.weight_currency_digits', 2)))

    def __init__(self):
        super(WeightPriceList, self).__init__()
        self._order.insert(0, ('weight', 'ASC'))

WeightPriceList()
