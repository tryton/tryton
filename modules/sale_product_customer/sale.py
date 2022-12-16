# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import If, Bool, Eval


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    product_customer = fields.Many2One(
        'sale.product_customer', "Customer's Product",
        ondelete='RESTRICT',
        domain=[
            If(Bool(Eval('product')),
                ['OR',
                    [
                        ('template.products', '=', Eval('product')),
                        ('product', '=', None),
                        ],
                    ('product', '=', Eval('product')),
                    ],
                []),
            ('party', '=', Eval('_parent_sale', {}).get('party')),
            ],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': Eval('sale_state') != 'draft',
            },
        depends=['product', 'type', 'sale_state'])

    @fields.depends('sale', '_parent_sale.party')
    def _get_product_customer_pattern(self):
        return {
            'party': (
                self.sale.party.id if self.sale and self.sale.party else -1),
            }

    @fields.depends('product', 'product_customer',
        methods=['_get_product_customer_pattern'])
    def on_change_product(self):
        super().on_change_product()
        if not self.product:
            return
        product_customers = list(self.product.product_customer_used(
                    **self._get_product_customer_pattern()))
        if len(product_customers) == 1:
            self.product_customer, = product_customers
        elif (self.product_customer
                and self.product_customer not in product_customers):
            self.product_customer = None

    @fields.depends('product', 'product_customer',
        methods=['on_change_product'])
    def on_change_product_customer(self):
        if self.product_customer:
            if self.product_customer.product:
                self.product = self.product_customer.product
            elif not self.product:
                if len(self.product_customer.template.products) == 1:
                    self.product, = self.product_customer.template.products
        self.on_change_product()


class AmendmentLine(metaclass=PoolMeta):
    __name__ = 'sale.amendment.line'

    product_customer = fields.Many2One(
        'sale.product_customer', "Customer's Product",
        domain=[
            ['OR',
                [
                    ('template.products', '=', Eval('product')),
                    ('product', '=', None),
                    ],
                ('product', '=', Eval('product')),
                ],
            ('party', '=', Eval('party', -1)),
            ],
        states={
            'invisible': Eval('action') != 'line',
            },
        depends=['action', 'product', 'party'])

    @fields.depends('line')
    def on_change_line(self):
        super().on_change_line()
        if self.line:
            self.product_customer = self.line.product_customer

    @fields.depends('product', 'product_customer', 'line')
    def on_change_product(self):
        try:
            super().on_change_product()
        except AttributeError:
            pass
        if not self.product or not self.line:
            return
        product_customers = list(self.product.product_customer_used(
                **self.line._get_product_customer_pattern()))
        if len(product_customers) == 1:
            self.product_customer, = product_customers
        elif (self.product_customer
                and self.product_customer not in product_customers):
            self.product_customer = None

    @fields.depends('product', 'product_customer',
        methods=['on_change_product'])
    def on_change_product_customer(self):
        if self.product_customer:
            if self.product_customer.product:
                self.product = self.product_customer.product
            elif not self.product:
                if len(self.product_customer.template.products) == 1:
                    self.product, = self.product_customer.template.products
        self.on_change_product()

    def _apply_line(self, sale, sale_line):
        super()._apply_line(sale, sale_line)
        sale_line.product_customer = self.product_customer
