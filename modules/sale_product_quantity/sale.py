# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelStorage, fields
from trytond.modules.sale.exceptions import SaleValidationError
from trytond.pool import Pool, PoolMeta


def product_quantity_mixin(states):
    class ProductQuantityMixin(ModelStorage):

        @fields.depends('product', 'quantity', 'unit')
        def on_change_product(self):
            pool = Pool()
            Uom = pool.get('product.uom')
            super().on_change_product()
            if self.product and self.quantity is None:
                if self.unit:
                    unit = self.unit
                else:
                    unit = self.product.sale_uom
                if self.product.sale_quantity_minimal:
                    self.quantity = Uom.compute_qty(
                        self.product.sale_uom,
                        self.product.sale_quantity_minimal,
                        unit)

        @classmethod
        def validate(cls, lines):
            super().validate(lines)
            for line in lines:
                line.check_quantity()

        def check_quantity(self):
            pool = Pool()
            Lang = pool.get('ir.lang')
            Uom = pool.get('product.uom')
            if (not self.product
                    or self.sale.state not in states
                    or self.quantity < 0):
                return
            lang = Lang.get()
            quantity = Uom.compute_qty(
                self.unit, self.quantity, self.product.sale_uom, round=False)
            if self.product.sale_quantity_minimal:
                if quantity < self.product.sale_quantity_minimal:
                    minimum = Uom.compute_qty(
                        self.product.sale_uom,
                        self.product.sale_quantity_minimal,
                        self.unit)
                    raise SaleValidationError(gettext(
                            'sale_product_quantity'
                            '.msg_sale_line_quantity_minimal',
                            line=self.rec_name,
                            quantity=lang.format_number_symbol(
                                self.quantity, self.unit),
                            minimum=lang.format_number_symbol(
                                minimum, self.unit)))
            if self.product.sale_quantity_rounding:
                remainder = round(
                    quantity % self.product.sale_quantity_rounding,
                    self.product.sale_quantity_digits)
                if (remainder
                        and remainder != self.product.sale_quantity_rounding):
                    rounding = Uom.compute_qty(
                        self.product.sale_uom,
                        self.product.sale_quantity_rounding,
                        self.unit, round=False)
                    raise SaleValidationError(gettext(
                            'sale_product_quantity'
                            '.msg_sale_line_quantity_rounding',
                            line=self.rec_name,
                            quantity=lang.format_number_symbol(
                                self.quantity, self.unit),
                            rounding=lang.format_number_symbol(
                                rounding, self.unit)))

    return ProductQuantityMixin


class Line(product_quantity_mixin(['draft']), metaclass=PoolMeta):
    __name__ = 'sale.line'


class POSLine(product_quantity_mixin(['open']), metaclass=PoolMeta):
    __name__ = 'sale.point.sale.line'
