# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If

from trytond.modules.product import price_digits, round_price


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    secondary_quantity = fields.Function(
        fields.Float("Secondary Quantity",
            digits=(16, Eval('secondary_unit_digits', 2)),
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('purchase_state') != 'draft',
                },
            depends=[
                'secondary_unit_digits', 'type', 'secondary_unit',
                'purchase_state']),
        'on_change_with_secondary_quantity', setter='set_secondary')
    secondary_unit = fields.Many2One(
        'product.uom', "Secondary Unit", ondelete='RESTRICT',
        domain=[
            If(Eval('purchase_state') == 'draft',
                ('category', '=', Eval('product_secondary_uom_category')),
                ()),
            ],
        states={
            'invisible': ((Eval('type') != 'line')
                | (~Eval('secondary_uom_factor')
                    & ~Eval('secondary_uom_rate'))),
            'readonly': Eval('purchase_state') != 'draft',
            },
        depends=['product_secondary_uom_category', 'type',
            'secondary_uom_factor', 'secondary_uom_rate', 'purchase_state'])
    secondary_unit_price = fields.Function(
        fields.Numeric(
            "Secondary Unit Price", digits=price_digits,
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('purchase_state') != 'draft',
                },
            depends=['type', 'secondary_unit', 'purchase_state']),
        'on_change_with_secondary_unit_price', setter='set_secondary')

    secondary_uom_factor = fields.Float("Secondary UOM Factor")
    secondary_uom_rate = fields.Float("Secondary UOM Rate")

    secondary_unit_digits = fields.Function(
        fields.Integer("Secondary Unit Digits"),
        'on_change_with_secondary_unit_digits')
    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UOM Category"),
        'on_change_with_product_secondary_uom_category')

    @fields.depends('product', 'product_supplier')
    def _secondary_record(self):
        if (self.product_supplier
                and self.product_supplier.purchase_secondary_uom):
            return self.product_supplier
        elif self.product and self.product.purchase_secondary_uom:
            return self.product

    @fields.depends('quantity', 'unit', 'secondary_unit',
        'secondary_uom_factor', 'secondary_uom_rate')
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

    @fields.depends('secondary_quantity', 'secondary_unit', 'unit',
        'secondary_uom_factor', 'secondary_uom_rate',
        methods=['on_change_quantity', 'on_change_with_amount'])
    def on_change_secondary_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_quantity and self.secondary_unit and self.unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.quantity = Uom.compute_qty(
                self.secondary_unit, self.secondary_quantity,
                self.unit, round=True,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)
            self.on_change_quantity()
            self.amount = self.on_change_with_amount()

    @fields.depends('unit_price', 'unit', 'secondary_unit',
        'secondary_uom_factor', 'secondary_uom_rate')
    def on_change_with_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.unit_price is not None and self.unit and self.secondary_unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            unit_price = Uom.compute_price(
                self.unit, self.unit_price, self.secondary_unit,
                factor=self.secondary_uom_factor, rate=self.secondary_uom_rate)
            return round_price(unit_price)
        else:
            return None

    @fields.depends('secondary_unit_price', 'secondary_unit', 'unit',
        'secondary_uom_factor', 'secondary_uom_rate',
        methods=['on_change_with_amount'])
    def on_change_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_unit_price is not None
                and self.secondary_unit and self.unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.unit_price = Uom.compute_price(
                self.secondary_unit, self.secondary_unit_price, self.unit,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)
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

    @fields.depends(methods=['_secondary_record'])
    def on_change_with_product_secondary_uom_category(self, name=None):
        secondary_record = self._secondary_record()
        if secondary_record:
            return secondary_record.purchase_secondary_uom.category.id

    @classmethod
    def set_secondary(cls, lines, name, value):
        pass

    @fields.depends('secondary_unit',
        methods=['on_change_with_secondary_quantity', '_secondary_record'])
    def on_change_product(self):
        super().on_change_product()
        secondary_record = self._secondary_record()
        if secondary_record and self.secondary_unit:
            if (self.secondary_unit.category
                    != secondary_record.purchase_secondary_uom.category):
                self.secondary_unit = None

        if secondary_record:
            self.secondary_uom_factor = (
                secondary_record.purchase_secondary_uom_normal_factor)
            self.secondary_uom_rate = (
                secondary_record.purchase_secondary_uom_normal_rate)
        else:
            self.secondary_unit = None
            self.secondary_uom_factor = None
            self.secondary_uom_rate = None
        self.secondary_quantity = self.on_change_with_secondary_quantity()

    def get_invoice_line(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        lines = super().get_invoice_line()
        if hasattr(InvoiceLine, 'secondary_unit'):
            for line in lines:
                if line.type != 'line':
                    continue
                if line.unit == self.unit:
                    line.secondary_unit = self.secondary_unit
        return lines

    def get_move(self, move_type):
        move = super().get_move(move_type)
        if move and hasattr(move.__class__, 'secondary_unit'):
            if move.uom == self.unit:
                move.secondary_unit = self.secondary_unit
        return move


class RequisitionLine(metaclass=PoolMeta):
    __name__ = 'purchase.requisition.line'

    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UOM Category"),
        'on_change_with_product_secondary_uom_category')

    @classmethod
    def _unit_categories(cls):
        return super()._unit_categories() + ['product_secondary_uom_category']

    @fields.depends('product')
    def on_change_with_product_secondary_uom_category(self, name=None):
        if self.product and self.product.purchase_secondary_uom:
            return self.product.purchase_secondary_uom.category.id

    def compute_request(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        request = super().compute_request()

        if request and request.product:
            product = request.product
            secondary_uom = product.purchase_secondary_uom
            if (secondary_uom
                    and request.uom.category == secondary_uom.category):
                request.quantity, request.uom = (
                    Uom.compute_qty(
                        request.uom, request.quantity,
                        product.purchase_uom, round=True,
                        factor=product.purchase_secondary_uom_normal_factor,
                        rate=product.purchase_secondary_uom_normal_rate),
                    product.purchase_uom)
        return request
