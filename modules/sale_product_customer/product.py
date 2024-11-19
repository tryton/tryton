# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.modules.product import ProductDeactivatableMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.tools import is_full_text, lstrip_wildcard


class ProductCustomer(
        sequence_ordered(), ProductDeactivatableMixin, MatchMixin,
        ModelSQL, ModelView):
    __name__ = 'sale.product_customer'

    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ],
        states={
            'readonly': Eval('id', -1) >= 0,
            })
    product = fields.Many2One(
        'product.product', "Variant",
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        states={
            'readonly': Eval('id', -1) >= 0,
            })
    party = fields.Many2One(
        'party.party', "Customer", required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', -1) >= 0,
            })
    name = fields.Char("Name", translate=True)
    code = fields.Char("Code")

    @fields.depends(
        'product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    def get_rec_name(self, name):
        if not self.name and not self.code:
            if self.product:
                name = self.product.rec_name
            else:
                name = self.template.rec_name
        else:
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
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('template', operator, operand, *extra),
            ('product', operator, operand, *extra),
            ('party', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ('name', operator, operand, *extra),
            ]


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    product_customers = fields.One2Many(
        'sale.product_customer', 'template', "Customers",
        states={
            'invisible': ~Eval('salable', False),
            })

    def product_customer_used(self, **pattern):
        for product_customer in self.product_customers:
            if product_customer.match(pattern):
                yield product_customer

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        ProductCustomer = pool.get('sale.product_customer')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_customers = 'product_customers' not in default
        default.setdefault('product_customers', None)
        new_templates = super().copy(templates, default)
        if copy_customers:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    pc for pc in template.product_customers if not pc.product)
                old2new[template.id] = new_template.id
            if to_copy:
                ProductCustomer.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    product_customers = fields.One2Many(
        'sale.product_customer', 'product', "Customers",
        domain=[
            ('template', '=', Eval('template', -1)),
            ],
        states={
            'invisible': ~Eval('salable', False),
            })

    def product_customer_used(self, **pattern):
        for product_customer in self.product_customers:
            if product_customer.match(pattern):
                yield product_customer
        pattern['product'] = None
        yield from self.template.product_customer_used(**pattern)

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        ProductCustomer = pool.get('sale.product_customer')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_customers = 'product_customers' not in default
        if 'template' in default:
            default.setdefault('product_customers', None)
        new_products = super().copy(products, default)
        if 'template' in default and copy_customers:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(products, new_products):
                if product.product_customers:
                    to_copy.extend(product.product_customers)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                ProductCustomer.copy(to_copy, {
                        'product': lambda d: product2new[d['product']],
                        'template': lambda d: template2new[d['template']],
                        })
        return new_products
