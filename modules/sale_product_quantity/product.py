# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    sale_quantity_minimal = fields.Float(
        "Sale Minimal Quantity",
        digits=(16, Eval('sale_quantity_digits', 0)),
        states={
            'invisible': ~Eval('salable', False),
            },
        domain=['OR',
            ('sale_quantity_minimal', '=', None),
            ('sale_quantity_minimal', '>', 0),
            ])
    sale_quantity_rounding = fields.Float(
        "Sale Rounding Quantity",
        digits=(16, Eval('sale_quantity_digits', 0)),
        states={
            'invisible': ~Eval('salable', False),
            },
        domain=['OR',
            ('sale_quantity_rounding', '=', None),
            ('sale_quantity_rounding', '>', 0),
            ])
    sale_quantity_digits = fields.Function(
        fields.Integer("Sale Quantity Digits"),
        'on_change_with_sale_quantity_digits')

    @fields.depends('default_uom', 'sale_uom')
    def on_change_with_sale_quantity_digits(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.default_uom:
            rounding = self.default_uom.rounding
            if self.sale_uom:
                rounding = Uom.compute_qty(
                    self.default_uom, rounding, self.sale_uom, round=False)
            return -Decimal(str(rounding)).as_tuple().exponent


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
