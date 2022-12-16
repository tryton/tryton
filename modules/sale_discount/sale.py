# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.product import price_digits, round_price


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    base_price = fields.Numeric(
        "Base Price", digits=price_digits,
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['type', 'sale_state'])

    discount_rate = fields.Function(fields.Numeric(
            "Discount Rate", digits=(16, 4),
            states={
                'invisible': Eval('type') != 'line',
                'readonly': Eval('sale_state') != 'draft',
                },
            depends=['type', 'sale_state']),
        'on_change_with_discount_rate', setter='set_discount_rate')
    discount_amount = fields.Function(fields.Numeric(
            "Discount Amount", digits=price_digits,
            states={
                'invisible': Eval('type') != 'line',
                'readonly': Eval('sale_state') != 'draft',
                },
            depends=['type', 'sale_state']),
        'on_change_with_discount_amount', setter='set_discount_amount')

    discount = fields.Function(fields.Char(
            "Discount",
            states={
                'invisible': ~Eval('discount'),
                }),
        'on_change_with_discount')

    @fields.depends(
        methods=[
            'compute_base_price', 'on_change_with_discount_rate',
            'on_change_with_discount_amount', 'on_change_with_discount'])
    def on_change_product(self):
        super().on_change_product()
        if self.product:
            self.base_price = self.compute_base_price()
            self.discount_rate = self.on_change_with_discount_rate()
            self.discount_amount = self.on_change_with_discount_amount()
            self.discount = self.on_change_with_discount()

    @fields.depends('product', 'unit')
    def compute_base_price(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.product:
            price = self.product.list_price
            if self.unit:
                price = Uom.compute_price(
                    self.product.default_uom, price, self.unit)
            return round_price(price)

    @fields.depends(
        methods=[
            'compute_base_price', 'on_change_with_discount_rate',
            'on_change_with_discount_amount', 'on_change_with_discount'])
    def on_change_quantity(self):
        super().on_change_quantity()
        self.base_price = self.compute_base_price()
        self.discount_rate = self.on_change_with_discount_rate()
        self.discount_amount = self.on_change_with_discount_amount()
        self.discount = self.on_change_with_discount()

    @fields.depends('unit_price', 'base_price')
    def on_change_with_discount_rate(self, name=None):
        if self.unit_price is None or not self.base_price:
            return
        rate = 1 - self.unit_price / self.base_price
        return rate.quantize(
            Decimal(1) / 10 ** self.__class__.discount_rate.digits[1])

    @fields.depends(
        'base_price', 'discount_rate',
        methods=['on_change_with_discount_amount', 'on_change_with_discount',
            'on_change_with_amount'])
    def on_change_discount_rate(self):
        if self.base_price is not None and self.discount_rate is not None:
            self.unit_price = round_price(
                self.base_price * (1 - self.discount_rate))
            self.discount_amount = self.on_change_with_discount_amount()
            self.discount = self.on_change_with_discount()
            self.amount = self.on_change_with_amount()

    @classmethod
    def set_discount_rate(cls, lines, name, value):
        pass

    @fields.depends('unit_price', 'base_price')
    def on_change_with_discount_amount(self, name=None):
        if self.unit_price is None or self.base_price is None:
            return
        return round_price(self.base_price - self.unit_price)

    @fields.depends(
        'base_price', 'discount_amount',
        methods=['on_change_with_discount_rate', 'on_change_with_discount',
            'on_change_with_amount'])
    def on_change_discount_amount(self):
        if self.base_price is not None and self.discount_amount is not None:
            self.unit_price = round_price(
                self.base_price - self.discount_amount)
            self.discount_rate = self.on_change_with_discount_rate()
            self.discount = self.on_change_with_discount()
            self.amount = self.on_change_with_amount()

    @classmethod
    def set_discount_amount(cls, lines, name, value):
        pass

    @fields.depends(
        'sale', '_parent_sale.currency',
        methods=[
            'on_change_with_discount_rate', 'on_change_with_discount_amount'])
    def on_change_with_discount(self, name=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        rate = self.on_change_with_discount_rate()
        if not rate or rate % Decimal('0.01'):
            amount = self.on_change_with_discount_amount()
            if amount:
                return lang.currency(
                    amount, self.sale.currency, digits=price_digits[1])
        else:
            return lang.format('%i', rate * 100) + '%'
