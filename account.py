# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.product import price_digits, round_price


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    secondary_quantity = fields.Function(
        fields.Float("Secondary Quantity",
            digits=(16, Eval('secondary_unit_digits', 2)),
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('invoice_state') != 'draft',
                },
            depends=[
                'secondary_unit_digits', 'type', 'secondary_unit',
                'invoice_state']),
        'on_change_with_secondary_quantity', setter='set_secondary')
    secondary_unit = fields.Many2One(
        'product.uom', "Secondary Unit", ondelete='RESTRICT',
        domain=[
            ('category', '=', Eval('product_secondary_uom_category')),
            ],
        states={
            'invisible': ((Eval('type') != 'line')
                | ~Eval('product_secondary_uom_category')),
            'readonly': Eval('invoice_state') != 'draft',
            },
        depends=['product_secondary_uom_category', 'type', 'invoice_state'])
    secondary_unit_price = fields.Function(
        fields.Numeric(
            "Secondary Unit Price", digits=price_digits,
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('invoice_state') != 'draft',
                },
            depends=['type', 'secondary_unit', 'invoice_state']),
        'on_change_with_secondary_unit_price', setter='set_secondary')

    secondary_unit_digits = fields.Function(
        fields.Integer("Secondary Unit Digits"),
        'on_change_with_secondary_unit_digits')
    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UOM Category"),
        'get_product_secondary_uom_category')

    @fields.depends('quantity', 'unit', 'secondary_unit', 'origin')
    def on_change_with_secondary_quantity(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.quantity and self.unit and self.secondary_unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            return Uom.compute_qty(
                self.unit, self.quantity,
                self.secondary_unit, round=True,
                factor=self.secondary_uom_factor, rate=self.secondary_uom_rate)
        else:
            return None

    @fields.depends('secondary_quantity', 'secondary_unit', 'unit', 'origin',
        methods=['on_change_with_amount'])
    def on_change_secondary_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_quantity and self.secondary_unit and self.unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.quantity = Uom.compute_qty(
                self.secondary_unit, self.secondary_quantity,
                self.unit, round=True,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)
            self.amount = self.on_change_with_amount()

    @fields.depends('unit_price', 'unit', 'secondary_unit', 'origin')
    def on_change_with_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.unit_price is not None and self.unit and self.secondary_unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            unit_price = Uom.compute_price(
                self.unit, self.unit_price, self.secondary_unit,
                factor=self.secondary_uom_factor, rate=self.secondary_uom_rate
                )
            return round_price(unit_price)
        else:
            return None

    @fields.depends('secondary_unit_price', 'secondary_unit', 'unit', 'origin',
        methods=['on_change_with_amount'])
    def on_change_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_unit_price is not None
                and self.secondary_unit and self.unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.unit_price = Uom.compute_price(
                self.secondary_unit, self.secondary_unit_price, self.unit,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor
                )
            self.unit_price = round_price(self.unit_price)
            self.amount = self.on_change_with_amount()

    @fields.depends(methods=[
            'on_change_secondary_quantity', 'on_change_secondary_unit_price'])
    def on_change_secondary_unit(self):
        self.on_change_secondary_quantity()
        self.on_change_secondary_unit_price()

    @fields.depends('secondary_unit')
    def on_change_with_secondary_unit_digits(self, name=None):
        if self.secondary_unit:
            return self.secondary_unit.digits

    def get_product_secondary_uom_category(self, name):
        return None

    @classmethod
    def set_secondary(cls, lines, name, value):
        pass

    @property
    def secondary_uom_factor(self):
        return None

    @property
    def secondary_uom_rate(self):
        return None
