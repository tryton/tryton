# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import builtins
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'

    quantity_minimal = fields.Float(
        "Minimal Quantity",
        digits=(None, Eval('quantity_digits', None)),
        domain=['OR',
            ('quantity_minimal', '=', None),
            ('quantity_minimal', '>', 0),
            ])
    quantity_rounding = fields.Float(
        "Rounding Quantity",
        digits=(None, Eval('quantity_digits', None)),
        domain=['OR',
            ('quantity_rounding', '=', None),
            ('quantity_rounding', '>', 0),
            ])
    quantity_digits = fields.Function(
        fields.Integer("Quantity Digits"),
        'on_change_with_quantity_digits')

    @fields.depends(
        'unit',
        'product', '_parent_product.default_uom',
        'template', '_parent_template.default_uom')
    def on_change_with_quantity_digits(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.product and self.product.default_uom:
            default_uom = self.product.default_uom
        elif self.template and self.template.default_uom:
            default_uom = self.template.default_uom
        else:
            return
        rounding = default_uom.rounding
        if self.unit:
            rounding = Uom.compute_qty(
                default_uom, rounding, self.unit, round=False)
        return -Decimal(str(rounding)).as_tuple().exponent

    def adapt_quantity(self, quantity, unit, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = Uom.compute_qty(unit, quantity, self.unit, round=False)
        if self.quantity_minimal:
            if quantity < self.quantity_minimal:
                quantity = self.quantity_minimal
        if self.quantity_rounding:
            remainder = builtins.round(
                quantity % self.quantity_rounding, self.quantity_digits)
            if remainder and remainder != self.quantity_rounding:
                quantity += (self.quantity_rounding - remainder)
        quantity = Uom.compute_qty(self.unit, quantity, unit, round=round)
        return quantity
