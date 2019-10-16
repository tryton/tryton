# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import (fields, ModelSQL, ModelView, sequence_ordered,
    MatchMixin)
from trytond.pool import PoolMeta
from trytond.pyson import If, Eval, Bool
from trytond.tools import lstrip_wildcard


class ProductCustomer(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Product Customer'
    __name__ = 'sale.product_customer'

    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ())
            ],
        depends=['product'])
    product = fields.Many2One(
        'product.product', "Variant", select=True,
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        depends=['template'])
    party = fields.Many2One('party.party', "Customer", required=True,
        ondelete='CASCADE')
    name = fields.Char("Name", translate=True)
    code = fields.Char("Code")

    @fields.depends(
        'product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    def get_rec_name(self, name):
        if self.name:
            name = self.name
        elif self.product:
            name = self.product.name
        else:
            name = self.template.name
        if self.code:
            name = '[' + self.code + '] ' + name
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        domain = [bool_op,
            ('template',) + tuple(clause[1:]),
            ('product',) + tuple(clause[1:]),
            ('party',) + tuple(clause[1:]),
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ('name',) + tuple(clause[1:]),
            ]
        return domain


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    product_customers = fields.One2Many(
        'sale.product_customer', 'template', "Customers",
        states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            },
        depends=['active', 'salable'])

    def product_customer_used(self, **pattern):
        for product_customer in self.product_customers:
            if product_customer.match(pattern):
                yield product_customer


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    product_customers = fields.One2Many(
        'sale.product_customer', 'product', "Customers",
        domain=[
            ('template', '=', Eval('template')),
            ],
        states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            },
        depends=['template', 'active', 'salable'])

    def product_customer_used(self, **pattern):
        for product_customer in self.product_customers:
            if product_customer.match(pattern):
                yield product_customer
        pattern['product'] = None
        yield from self.template.product_customer_used(**pattern)
