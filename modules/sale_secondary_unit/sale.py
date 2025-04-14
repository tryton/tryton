# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    secondary_quantity = fields.Function(fields.Float(
            "Secondary Quantity", digits='secondary_unit',
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('sale_state') != 'draft',
                },
            depends=['secondary_uom_factor', 'secondary_uom_rate']),
        'on_change_with_secondary_quantity', setter='set_secondary')
    secondary_unit = fields.Many2One(
        'product.uom', "Secondary Unit", ondelete='RESTRICT',
        domain=[
            If(Eval('sale_state') == 'draft',
                ('category', '=', Eval('product_secondary_uom_category')),
                ()),
            ],
        states={
            'invisible': ((Eval('type') != 'line')
                | ~Eval('product_secondary_uom_category')),
            'readonly': Eval('sale_state') != 'draft',
            })
    secondary_unit_price = fields.Function(Monetary(
            "Secondary Unit Price", currency='currency', digits=price_digits,
            states={
                'invisible': ((Eval('type') != 'line')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('sale_state') != 'draft',
                }),
        'on_change_with_secondary_unit_price', setter='set_secondary')

    secondary_uom_factor = fields.Float(
        "Secondary UoM Factor",
        states={
            'readonly': True,
            'required': (Eval('type') == 'line') & Eval('secondary_unit'),
            },
        help="The factor for the secondary Unit of Measure.")
    secondary_uom_rate = fields.Float(
        "Secondary UoM Rate",
        states={
            'readonly': True,
            'required': (Eval('type') == 'line') & Eval('secondary_unit'),
            },
        help="The rate for the secondary Unit of Measure.")

    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UoM Category",
            help="The category of secondary Unit of Measure for the product."),
        'on_change_with_product_secondary_uom_category')

    @fields.depends('product')
    def _secondary_record(self):
        if self.product and self.product.sale_secondary_uom:
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

    @fields.depends(methods=['_secondary_record'])
    def on_change_with_product_secondary_uom_category(self, name=None):
        secondary_record = self._secondary_record()
        if secondary_record:
            return secondary_record.sale_secondary_uom.category

    @classmethod
    def set_secondary(cls, lines, name, value):
        pass

    @fields.depends(
        'secondary_unit', 'product',
        methods=['on_change_with_secondary_quantity', '_secondary_record'])
    def on_change_product(self):
        super().on_change_product()
        secondary_record = self._secondary_record()
        if secondary_record:
            secondary_uom = secondary_record.sale_secondary_uom
            if self.secondary_unit and secondary_uom:
                if self.secondary_unit.category != secondary_uom.category:
                    self.secondary_unit = None
            if not self.secondary_unit and secondary_record != self.product:
                self.secondary_unit = secondary_uom

        if secondary_record:
            self.secondary_uom_factor = (
                secondary_record.sale_secondary_uom_normal_factor)
            self.secondary_uom_rate = (
                secondary_record.sale_secondary_uom_normal_rate)
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

    def get_move(self, shipment_type):
        move = super().get_move(shipment_type)
        if move and hasattr(move.__class__, 'secondary_unit'):
            if move.unit == self.unit:
                move.secondary_unit = self.secondary_unit
        return move


class Line_ProductCustomer(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @fields.depends('product_customer')
    def _secondary_record(self):
        if self.product_customer and self.product_customer.sale_secondary_uom:
            return self.product_customer
        return super()._secondary_record()


class OpportunityLine(metaclass=PoolMeta):
    __name__ = 'sale.opportunity.line'

    def _set_sale_line_quantity(self, sale_line):
        super()._set_sale_line_quantity(sale_line)
        if self.unit.category != self.product.sale_uom.category:
            sale_line.unit = self.product.sale_uom
            sale_line.secondary_quantity = self.quantity
            sale_line.secondary_unit = self.unit
            sale_line.on_change_secondary_quantity()


class BlanketAgreementLine(metaclass=PoolMeta):
    __name__ = 'sale.blanket_agreement.line'

    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UoM Category",
            help="The category of the secondary Unit of Measure "
            "for the product."),
        'on_change_with_product_secondary_uom_category')

    @classmethod
    def _unit_categories(cls):
        return super()._unit_categories() + ['product_secondary_uom_category']

    def is_same_uom_category(self, sale_line):
        return super().is_same_uom_category(sale_line) or (
            sale_line.secondary_unit and (
                self.unit.category == sale_line.secondary_unit.category))

    def remainig_quantity_for_sale(self, line, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        remaining_quantity = super().remainig_quantity_for_sale(
            line, round=round)
        if (self.remaining_quantity is not None
                and line.secondary_unit
                and self.unit.category == line.secondary_unit.category):
            remaining_quantity = Uom.compute_qty(
                self.unit, self.remaining_quantity, line.unit,
                factor=line.secondary_uom_rate,
                rate=line.secondary_uom_factor,
                round=round)
        return remaining_quantity

    @fields.depends('product')
    def on_change_with_product_secondary_uom_category(self, name=None):
        if self.product and self.product.sale_secondary_uom:
            return self.product.sale_secondary_uom.category

    def _set_sale_line_quantity(self, sale_line):
        super()._set_sale_line_quantity(sale_line)
        secondary_uom = self.product.sale_secondary_uom
        if (secondary_uom
                and self.unit.category == secondary_uom.category):
            sale_line.unit = self.product.sale_uom
            sale_line.secondary_quantity = self.remaining_quantity or 0
            sale_line.secondary_unit = self.unit
            sale_line.secondary_unit_price = self.unit_price
            sale_line.on_change_secondary_quantity()


class LineBlanketAgreement(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @fields.depends(
        'blanket_agreement_line', '_parent_blanket_agreement_line.unit',
        '_parent_blanket_agreement_line.unit_price', 'unit', 'secondary_unit',
        'secondary_uom_rate', 'secondary_uom_factor')
    def compute_unit_price(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        unit_price = super().compute_unit_price()
        line = self.blanket_agreement_line
        if (line
                and self.unit
                and self.secondary_unit
                and line.unit
                and self.secondary_unit.category == line.unit.category):
            secondary_unit_price = Uom.compute_price(
                line.unit, line.unit_price, self.secondary_unit)
            unit_price = Uom.compute_price(
                self.secondary_unit, secondary_unit_price, self.unit,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)
            unit_price = round_price(unit_price)
        return unit_price

    @fields.depends(
        'blanket_agreement_line',
        '_parent_blanket_agreement_line.unit',
        '_parent_blanket_agreement_line.remaining_quantity',
        'sale', 'unit', 'secondary_quantity', 'secondary_unit',
        'secondary_unit_price', methods=['on_change_secondary_quantity'])
    def on_change_blanket_agreement_line(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        super().on_change_blanket_agreement_line()
        if self.blanket_agreement_line:
            line = self.blanket_agreement_line
            if (self.secondary_unit and line.unit
                    and self.secondary_unit.category == line.unit.category):
                if line.remaining_quantity is not None:
                    remaining_quantity = Uom.compute_qty(
                        line.unit, line.remaining_quantity,
                        self.secondary_unit)
                    if (self.secondary_quantity is None
                            or self.secondary_quantity > remaining_quantity):
                        self.secondary_quantity = remaining_quantity
                        self.on_change_secondary_quantity()

    def quantity_for_blanket_agreement(self, line, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = super().quantity_for_blanket_agreement(line, round=round)
        if (self.secondary_unit
                and self.secondary_unit.category == line.unit.category):
            sale_line_quantity = (
                self.actual_quantity if self.actual_quantity is not None
                else self.quantity)
            quantity = Uom.compute_qty(
                self.unit, sale_line_quantity, line.unit,
                factor=self.secondary_uom_factor,
                rate=self.secondary_uom_rate,
                round=round)
        return quantity


class AmendmentLine(metaclass=PoolMeta):
    __name__ = 'sale.amendment.line'

    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UoM Category",
            help="The category of the secondary Unit of Measure "
            "for the product."),
        'on_change_with_product_secondary_uom_category')

    @classmethod
    def _unit_categories(cls):
        return super()._unit_categories() + ['product_secondary_uom_category']

    @fields.depends('product')
    def on_change_with_product_secondary_uom_category(self, name=None):
        if self.product and self.product.sale_secondary_uom:
            return self.product.sale_secondary_uom.category

    def _apply_line(self, sale, sale_line):
        super()._apply_line(sale, sale_line)
        if (self.unit and self.product
                and self.unit.category != self.product.sale_uom.category):
            sale_line.unit = self.line.unit
            sale_line.secondary_quantity = self.quantity
            sale_line.secondary_unit = self.unit
            sale_line.on_change_secondary_quantity()
            sale_line.secondary_unit_price = self.unit_price
            sale_line.on_change_secondary_unit_price()
