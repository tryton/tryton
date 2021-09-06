# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import (
    ModelView, ModelSQL, ModelStorage, sequence_ordered, fields)
from trytond.pyson import Eval, If, Bool
from trytond.pool import PoolMeta, Pool

from trytond.modules.product import round_price


class Template(metaclass=PoolMeta):
    __name__ = "product.template"

    components = fields.One2Many(
        'product.component', 'parent_template', "Components")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('kit', "Kit"))

    @fields.depends('type', 'cost_price_method')
    def on_change_type(self):
        super().on_change_type()
        if self.type == 'kit':
            self.cost_price_method = 'fixed'

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        Component = pool.get('product.component')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_components = 'components' not in default
        default.setdefault('components', None)
        new_templates = super().copy(templates, default)
        if copy_components:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    c for c in template.components if not c.product)
                old2new[template.id] = new_template.id
            if to_copy:
                Component.copy(to_copy, {
                        'parent_template': (lambda d:
                            old2new[d['parent_template']]),
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = "product.product"

    components = fields.One2Many(
        'product.component', 'parent_product', "Components")

    def get_multivalue(self, name, **pattern):
        pool = Pool()
        Uom = pool.get('product.uom')
        value = super().get_multivalue(name, **pattern)
        if name == 'cost_price' and self.type == 'kit':
            value = Decimal(0)
            for component in self.components_used:
                cost_price = component.product.get_multivalue(
                    'cost_price', **pattern)
                cost_price = Uom.compute_price(
                    component.product.default_uom, cost_price, component.unit)
                value += cost_price * Decimal(str(component.quantity))
            value = round_price(value)
        return value

    @property
    def components_used(self):
        return self.components or self.template.components

    @classmethod
    def get_quantity(cls, products, name):
        pool = Pool()
        Uom = pool.get('product.uom')
        kits = [p for p in products if p.type == 'kit']
        quantities = super().get_quantity(products, name)
        for kit in kits:
            qties = []
            for component in kit.components_used:
                component_qty = Uom.compute_qty(
                    component.product.default_uom,
                    getattr(component.product, name),
                    component.unit, round=False)
                if not component.fixed:
                    component_qty /= component.quantity
                qties.append(component_qty)
            quantities[kit.id] = kit.default_uom.floor(min(qties, default=0))
        return quantities

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        Component = pool.get('product.component')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_components = 'components' not in default
        if 'template' in default:
            default.setdefault('components', None)
        new_products = super().copy(products, default)
        if 'template' in default and copy_components:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(products, new_products):
                if product.components:
                    to_copy.extend(product.components)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                Component.copy(to_copy, {
                        'parent_product': (lambda d:
                            product2new[d['parent_product']]),
                        'parent_template': (lambda d:
                            template2new[d['parent_template']]),
                        })
        return new_products


class ComponentMixin(sequence_ordered(), ModelStorage):

    parent_type = fields.Function(fields.Selection(
            'get_product_types', "Parent Type"), 'on_change_with_parent_type')
    product = fields.Many2One(
        'product.product', "Product", required=True,
        domain=[
            ('components', '=', None),
            ('template.components', '=', None),
            If(Eval('parent_type') == 'kit',
                ('type', '=', 'goods'),
                ()),
            ],
        depends=['parent_type'])
    product_unit_category = fields.Function(
        fields.Many2One('product.uom.category', "Product Unit Category"),
        'on_change_with_product_unit_category')
    quantity = fields.Float(
        "Quantity", required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    unit = fields.Many2One('product.uom', "Unit", required=True,
        domain=[
            If(Bool(Eval('product_unit_category')),
                ('category', '=', Eval('product_unit_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'product_unit_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    fixed = fields.Boolean("Fixed",
        help="Check to make the quantity of the component independent "
        "of the kit quantity.")

    @classmethod
    def get_product_types(cls):
        pool = Pool()
        Product = pool.get('product.product')
        return Product.fields_get(['type'])['type']['selection']

    def on_change_with_parent_type(self, name):
        raise NotImplementedError

    @property
    def parent_uom(self):
        raise NotImplementedError

    @fields.depends('product', 'unit', 'quantity',
        methods=['on_change_with_product_unit_category'])
    def on_change_product(self):
        if self.product:
            self.product_unit_category = (
                self.on_change_with_product_unit_category())
            if (not self.unit
                    or self.unit.category != self.product_unit_category):
                self.unit = self.product.default_uom

    @fields.depends('product')
    def on_change_with_product_unit_category(self, name=None):
        if self.product:
            return self.product.default_uom.category.id

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits

    def get_line(self, Line, quantity, unit, **values):
        pool = Pool()
        Uom = pool.get('product.uom')
        line = Line(product=self.product, **values)
        line.unit = self.unit
        if self.fixed:
            line.quantity = self.quantity
        else:
            quantity = Uom.compute_qty(
                unit, quantity, self.parent_uom, round=False)
            line.quantity = self.unit.round(quantity * self.quantity)
        return line

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return (lang.format(
                '%.*f', (self.unit.digits, self.quantity))
            + '%s %s' % (
                self.unit.symbol, self.product.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('product.rec_name',) + tuple(clause[1:]),
            ]


class Component(ComponentMixin, ModelSQL, ModelView):
    "Product Component"
    __name__ = "product.component"

    parent_template = fields.Many2One(
        'product.template', "Parent Product",
        required=True, ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('parent_product')),
                ('products', '=', Eval('parent_product')),
                ()),
            ],
        depends=['parent_product'])
    parent_product = fields.Many2One(
        'product.product', "Parent Variant", ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('parent_template')),
                ('template', '=', Eval('parent_template')),
                ()),
            ],
        depends=['parent_template'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.update(['parent_template', 'parent_product'])

    @fields.depends(
        'parent_product', '_parent_parent_product.template')
    def on_change_parent_product(self):
        if self.parent_product:
            self.parent_template = self.parent_product.template

    @fields.depends(
        'parent_template', '_parent_parent_template.type',
        'parent_product', '_parent_parent_product.type')
    def on_change_with_parent_type(self, name=None):
        if self.parent_product:
            return self.parent_product.type
        elif self.parent_template:
            return self.parent_template.type

    @property
    def parent_uom(self):
        if self.parent_product:
            return self.parent_product.default_uom
        elif self.parent_template:
            return self.parent_template.default_uom

    def get_rec_name(self, name):
        return super().get_rec_name(name) + (
            ' @ %s' % (
                self.parent_product.rec_name if self.parent_product
                else self.parent_template.rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return super().search_rec_name(name, clause) + [
            ('parent_product.rec_name',) + tuple(clause[1:]),
            ('parent_template.rec_name',) + tuple(clause[1:]),
            ]
