# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import logging
from decimal import Decimal
from importlib import import_module

import stdnum
import stdnum.exceptions
from sql import Literal
from sql.conditionals import Coalesce
from sql.functions import CharLength
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, Index, Model, ModelSQL, ModelView, UnionMixin,
    fields, sequence_ordered, tree)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.pyson import Eval, Get, If
from trytond.tools import is_full_text, lstrip_wildcard
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

try:
    from trytond.tools import barcode
except ImportError:
    barcode = None

from .exceptions import InvalidIdentifierCode
from .ir import price_decimal

__all__ = ['price_digits', 'round_price', 'TemplateFunction']
logger = logging.getLogger(__name__)

TYPES = [
    ('goods', 'Goods'),
    ('assets', 'Assets'),
    ('service', 'Service'),
    ]
COST_PRICE_METHODS = [
    ('fixed', 'Fixed'),
    ('average', 'Average'),
    ]

price_digits = (None, price_decimal)


def round_price(value, rounding=None):
    "Round price using the price digits"
    if isinstance(value, int):
        return Decimal(value)
    return value.quantize(
        Decimal(1) / 10 ** price_digits[1], rounding=rounding)


class Template(
        DeactivableMixin, ModelSQL, ModelView, CompanyMultiValueMixin):
    __name__ = "product.template"
    name = fields.Char(
        "Name", size=None, required=True, translate=True)
    code_readonly = fields.Function(
        fields.Boolean("Code Readonly"), 'get_code_readonly')
    code = fields.Char(
        "Code", strip='leading',
        states={
            'readonly': Eval('code_readonly', False),
            })
    type = fields.Selection(TYPES, "Type", required=True)
    consumable = fields.Boolean('Consumable',
        domain=[
            If(Eval('type') != 'goods',
                ('consumable', '=', False),
                ()),
            ],
        states={
            'invisible': Eval('type', 'goods') != 'goods',
            },
        help="Check to allow stock moves to be assigned "
        "regardless of stock level.")
    list_price = fields.MultiValue(fields.Numeric(
            "List Price", digits=price_digits,
            states={
                'readonly': ~Eval('context', {}).get('company'),
                },
            help="The standard price the product is sold at."))
    list_prices = fields.One2Many(
        'product.list_price', 'template', "List Prices")
    cost_price = fields.Function(fields.Numeric(
            "Cost Price", digits=price_digits,
            help="The amount it costs to purchase or make the product, "
            "or carry out the service."),
        'get_cost_price')
    cost_price_method = fields.MultiValue(fields.Selection(
            COST_PRICE_METHODS, "Cost Price Method", required=True,
            help="The method used to calculate the cost price."))
    cost_price_methods = fields.One2Many(
        'product.cost_price_method', 'template', "Cost Price Methods")
    default_uom = fields.Many2One(
        'product.uom', "Default UoM", required=True,
        help="The standard Unit of Measure for the product.\n"
        "Used internally when calculating the stock levels of goods "
        "and assets.")
    default_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Default UoM Category",
            help="The category of the default Unit of Measure."),
        'on_change_with_default_uom_category',
        searcher='search_default_uom_category')
    categories = fields.Many2Many(
        'product.template-product.category', 'template', 'category',
        "Categories",
        help="The categories that the product is in.\n"
        "Used to group similar products together.")
    categories_all = fields.Many2Many(
        'product.template-product.category.all',
        'template', 'category', "Categories", readonly=True)
    products = fields.One2Many(
        'product.product', 'template', "Variants",
        help="The different variants the product comes in.")

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.code, Index.Similarity())),
                })
        cls._order.insert(0, ('rec_name', 'ASC'))

        types_cost_method = cls._cost_price_method_domain_per_type()
        cls.cost_price_method.domain = [
            Get(types_cost_method, Eval('type'), []),
            ]

    @classmethod
    def _cost_price_method_domain_per_type(cls):
        return {'service': [('cost_price_method', '=', 'fixed')]}

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'list_price':
            return pool.get('product.list_price')
        elif field == 'cost_price_method':
            return pool.get('product.cost_price_method')
        return super().multivalue_model(field)

    def multivalue_records(self, field):
        records = super().multivalue_records(field)
        if field == 'list_price':
            # Sort to get record with empty product first
            records = sorted(records, key=lambda r: r.product is not None)
        return records

    def get_multivalue(self, name, **pattern):
        if name == 'list_price':
            pattern.setdefault('product', None)
        return super().get_multivalue(name, **pattern)

    def set_multivalue(self, name, value, save=True, **pattern):
        if name == 'list_price':
            pattern.setdefault('product', None)
        return super().set_multivalue(name, value, save=save, **pattern)

    @classmethod
    def order_code(cls, tables):
        table, _ = tables[None]
        if cls.default_code_readonly():
            return [CharLength(table.code), table.code]
        else:
            return [table.code]

    @classmethod
    def order_rec_name(cls, tables):
        table, _ = tables[None]
        return cls.order_code(tables) + [table.name]

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

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
            ('name', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ('products.code', operator, code_value, *extra),
            ('products.identifiers.code', operator, code_value, *extra),
            ]

    @staticmethod
    def default_type():
        return 'goods'

    @staticmethod
    def default_consumable():
        return False

    def get_cost_price(self, name):
        if len(self.products) == 1:
            product, = self.products
            return product.cost_price

    @classmethod
    def default_cost_price_method(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        return Configuration(1).get_multivalue(
            'default_cost_price_method', **pattern)

    @classmethod
    def default_products(cls):
        transaction = Transaction()
        if (transaction.user == 0
                or not transaction.context.get('default_products', True)):
            return []
        return [{}]

    @classmethod
    def default_code_readonly(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return bool(config.template_sequence)

    def get_code_readonly(self, name):
        return self.default_code_readonly()

    @fields.depends('type', 'cost_price_method')
    def on_change_type(self):
        if self.type == 'service':
            self.cost_price_method = 'fixed'

    @fields.depends('default_uom')
    def on_change_with_default_uom_category(self, name=None):
        return self.default_uom.category if self.default_uom else None

    @classmethod
    def search_default_uom_category(cls, name, clause):
        return [('default_uom.category' + clause[0][len(name):], *clause[1:])]

    @classmethod
    def _code_sequence(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return config.template_sequence

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            values.setdefault('products', None)
            if not values.get('code'):
                if sequence := cls._code_sequence():
                    values['code'] = sequence.get()
        return values

    @classmethod
    def on_modification(cls, mode, templates, field_names=None):
        pool = Pool()
        Product = pool.get('product.product')
        super().on_modification(mode, templates, field_names=field_names)
        if mode in {'create', 'write'}:
            products = sum((t.products for t in templates), ())
            Product.sync_code(products)

    @classmethod
    def copy(cls, templates, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('code', None)
        return super().copy(templates, default=default)

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super().search_global(text):
            icon = icon or 'tryton-product'
            yield record, rec_name, icon


class TemplateFunction(fields.Function):

    def __init__(self, field):
        super().__init__(
            field, 'get_template', searcher='search_template')
        # Disable on_change as it is managed by on_change_template
        self.on_change = set()
        self.on_change_with = set()

    def __copy__(self):
        return TemplateFunction(copy.copy(self._field))

    def __deepcopy__(self, memo):
        return TemplateFunction(copy.deepcopy(self._field, memo))

    @staticmethod
    def order(name):
        @classmethod
        def order(cls, tables):
            pool = Pool()
            Template = pool.get('product.template')
            product, _ = tables[None]
            if 'template' not in tables:
                template = Template.__table__()
                tables['template'] = {
                    None: (template, product.template == template.id),
                    }
            return getattr(Template, name).convert_order(
                name, tables['template'], Template)
        return order

    def searchable(self, model):
        pool = Pool()
        Template = pool.get('product.template')
        return super().searchable(model) and self._field.searchable(Template)


class TemplateDeactivatableMixin(DeactivableMixin):
    __slots__ = ()

    @classmethod
    def _active_expression(cls, tables):
        pool = Pool()
        Template = pool.get('product.template')
        table, _ = tables[None]
        if 'template' not in tables:
            template = Template.__table__()
            tables['template'] = {
                None: (template, table.template == template.id),
                }
        else:
            template, _ = tables['template'][None]
        return table.active & template.active

    @classmethod
    def domain_active(cls, domain, tables):
        expression = cls._active_expression(tables)
        _, operator, value = domain
        if operator in {'=', '!='}:
            if (operator == '=') != value:
                expression = ~expression
        elif operator in {'in', 'not in'}:
            if True in value and False not in value:
                pass
            elif False in value and True not in value:
                expression = ~expression
            else:
                expression = Literal(True)
        else:
            expression = Literal(True)
        return expression


class ProductDeactivatableMixin(TemplateDeactivatableMixin):
    __slots__ = ()

    @classmethod
    def _active_expression(cls, tables):
        pool = Pool()
        Product = pool.get('product.product')
        table, _ = tables[None]
        if 'product' not in tables:
            product = Product.__table__()
            tables['product'] = {
                None: (product, table.product == product.id),
                }
        else:
            product, _ = tables['product'][None]
        expression = super()._active_expression(tables)
        return expression & Coalesce(product.active, expression)


class Product(
        TemplateDeactivatableMixin, tree('replaced_by'), ModelSQL, ModelView,
        CompanyMultiValueMixin):
    __name__ = "product.product"
    _order_name = 'rec_name'
    template = fields.Many2One(
        'product.template', "Product Template",
        required=True, ondelete='CASCADE',
        search_context={'default_products': False},
        help="The product that defines the common properties "
        "inherited by the variant.")
    code_readonly = fields.Function(fields.Boolean('Code Readonly'),
        'get_code_readonly')
    prefix_code = fields.Function(fields.Char(
            "Prefix Code",
            states={
                'invisible': ~Eval('prefix_code'),
                }),
        'on_change_with_prefix_code')
    suffix_code = fields.Char(
        "Suffix Code", strip='trailing',
        states={
            'readonly': Eval('code_readonly', False),
            },
        help="The unique identifier for the product (aka SKU).")
    code = fields.Char(
        "Code", readonly=True,
        help="A unique identifier for the variant.")
    identifiers = fields.One2Many(
        'product.identifier', 'product', "Identifiers",
        help="Other identifiers associated with the variant.")
    list_price = fields.MultiValue(fields.Numeric(
            "List Price", digits=price_digits,
            states={
                'readonly': ~Eval('context', {}).get('company'),
                },
            help="The standard price the variant is sold at.\n"
            "Leave empty to use the list price of the product."))
    list_prices = fields.One2Many(
        'product.list_price', 'product', "List Prices")
    list_price_used = fields.Function(fields.Numeric(
            "List Price", digits=price_digits,
            help="The standard price the variant is sold at."),
        'get_list_price_used')
    cost_price = fields.MultiValue(fields.Numeric(
            "Cost Price", digits=price_digits,
            states={
                'readonly': ~Eval('context', {}).get('company'),
                },
            help="The amount it costs to purchase or make the variant, "
            "or carry out the service."))
    cost_prices = fields.One2Many(
        'product.cost_price', 'product', "Cost Prices")
    description = fields.Text("Description", translate=True)
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=price_digits), 'get_price_uom')
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=price_digits), 'get_price_uom')
    replaced_by = fields.Many2One(
        'product.product', "Replaced By",
        domain=[
            ('type', '=', Eval('type')),
            ('default_uom_category', '=', Eval('default_uom_category', -1)),
            ],
        states={
            'invisible': ~Eval('replaced_by'),
            },
        help="The product replacing this one.")
    replacing = fields.One2Many(
        'product.product', 'replaced_by', "Replacing", readonly=True,
        states={
            'invisible': ~Eval('replacing'),
            },
        help="The products that this one is replacing.")

    @classmethod
    def __setup__(cls):
        pool = Pool()
        Template = pool.get('product.template')

        if not hasattr(cls, '_no_template_field'):
            cls._no_template_field = set()
        cls._no_template_field.update(['products'])

        cls.suffix_code.search_unaccented = False
        cls.code.search_unaccented = False

        product_fields = {}
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            field = getattr(cls, attr)
            if (not isinstance(field, fields.Field)
                    or isinstance(field, TemplateFunction)):
                continue
            product_fields[attr] = field

        super().__setup__()
        cls.__access__.add('template')
        cls._order.insert(0, ('rec_name', 'ASC'))

        t = cls.__table__()
        cls._sql_constraints = [
            ('code_exclude', Exclude(t, (t.code, Equal),
                    where=(t.active == Literal(True))
                    & (t.code != '')),
                'product.msg_product_code_unique'),
            ]
        cls._sql_indexes.add(
            Index(t, (t.code, Index.Similarity(cardinality='high'))))

        for attr in dir(Template):
            tfield = getattr(Template, attr)
            if not isinstance(tfield, fields.Field):
                continue
            if attr in cls._no_template_field:
                continue
            field = getattr(cls, attr, None)
            if (isinstance(field, TemplateFunction)
                    and attr in product_fields):
                setattr(cls, attr, copy.deepcopy(product_fields[attr]))
            elif not field or isinstance(field, TemplateFunction):
                tfield = copy.deepcopy(tfield)
                if hasattr(tfield, 'field'):
                    tfield.field = None
                invisible_state = ~Eval('template')
                if 'invisible' in tfield.states:
                    tfield.states['invisible'] |= invisible_state
                else:
                    tfield.states['invisible'] = invisible_state
                setattr(cls, attr, TemplateFunction(tfield))
                order_method = getattr(cls, 'order_%s' % attr, None)
                if (not order_method
                        and not isinstance(tfield, (
                                fields.Function,
                                fields.One2Many,
                                fields.Many2Many))):
                    order_method = TemplateFunction.order(attr)
                    setattr(cls, 'order_%s' % attr, order_method)
                if isinstance(tfield, fields.One2Many):
                    getattr(cls, attr).setter = '_set_template_function'

    @classmethod
    def _set_template_function(cls, products, name, value):
        # Prevent NotImplementedError for One2Many
        pass

    @classmethod
    def order_suffix_code(cls, tables):
        table, _ = tables[None]
        if cls.default_code_readonly():
            return [CharLength(table.suffix_code), table.suffix_code]
        else:
            return [table.suffix_code]

    @classmethod
    def order_code(cls, tables):
        pool = Pool()
        Template = pool.get('product.template')
        table, _ = tables[None]
        if cls.default_code_readonly() or Template.default_code_readonly():
            return [CharLength(table.code), table.code]
        else:
            return [table.code]

    @fields.depends('template', '_parent_template.id')
    def on_change_template(self):
        for name, field in self._fields.items():
            if isinstance(field, TemplateFunction):
                if self.template:
                    value = getattr(self.template, name, None)
                else:
                    value = None
                setattr(self, name, value)

    def get_template(self, name):
        value = getattr(self.template, name)
        if isinstance(value, Model):
            field = getattr(self.__class__, name)
            if field._type == 'reference':
                return str(value)
            return value.id
        elif (isinstance(value, (list, tuple))
                and value and isinstance(value[0], Model)):
            return [r.id for r in value]
        else:
            return value

    @fields.depends('template', '_parent_template.code')
    def on_change_with_prefix_code(self, name=None):
        if self.template:
            return self.template.code

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'list_price':
            return pool.get('product.list_price')
        elif field == 'cost_price':
            return pool.get('product.cost_price')
        return super().multivalue_model(field)

    def set_multivalue(self, name, value, save=True, **pattern):
        context = Transaction().context
        if name in {'cost_price', 'list_price'} and not value:
            if not pattern.get('company', context.get('company')):
                return []
        if name == 'list_price':
            pattern.setdefault('template', self.template.id)
        return super().set_multivalue(name, value, save=save, **pattern)

    def get_multivalue(self, name, **pattern):
        if isinstance(self._fields[name], TemplateFunction):
            return self.template.get_multivalue(name, **pattern)
        else:
            if name == 'list_price':
                pattern.setdefault('template', self.template.id)
            return super().get_multivalue(name, **pattern)

    @classmethod
    def default_cost_price(cls, **pattern):
        context = Transaction().context
        if pattern.get('company', context.get('company')):
            return Decimal(0)

    @classmethod
    def search_template(cls, name, clause):
        return [('template.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def order_rec_name(cls, tables):
        pool = Pool()
        Template = pool.get('product.template')
        product, _ = tables[None]
        if 'template' not in tables:
            template = Template.__table__()
            tables['template'] = {
                None: (template, product.template == template.id),
                }
        return cls.order_code(tables) + Template.name.convert_order('name',
            tables['template'], Template)

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

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
            ('code', operator, code_value, *extra),
            ('identifiers.code', operator, code_value, *extra),
            ('template.name', operator, operand, *extra),
            ('template.code', operator, code_value, *extra),
            ('replacing.code', operator, code_value, *extra),
            ('replacing.identifiers.code', operator, code_value, *extra),
            ]

    @staticmethod
    def get_price_uom(products, name):
        Uom = Pool().get('product.uom')
        res = {}
        field = name[:-4]
        if Transaction().context.get('uom'):
            to_uom = Uom(Transaction().context['uom'])
        else:
            to_uom = None
        for product in products:
            price = getattr(product, field)
            if to_uom and product.default_uom.category == to_uom.category:
                res[product.id] = Uom.compute_price(
                    product.default_uom, price, to_uom)
            else:
                res[product.id] = price
        return res

    @classmethod
    def search_global(cls, text):
        for id_, rec_name, icon in super().search_global(text):
            icon = icon or 'tryton-product'
            yield id_, rec_name, icon

    @classmethod
    def default_code_readonly(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return bool(config.product_sequence)

    def get_code_readonly(self, name):
        return self.default_code_readonly()

    def identifier_get(self, types=None):
        "Return the first identifier for the given types"
        if isinstance(types, str) or types is None:
            types = {types}
        for identifier in self.identifiers:
            if identifier.type in types:
                return identifier

    @classmethod
    def _code_sequence(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return config.product_sequence

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('suffix_code'):
            if sequence := cls._code_sequence():
                values['suffix_code'] = sequence.get()
        return values

    @classmethod
    def on_modification(cls, mode, products, field_names=None):
        super().on_modification(mode, products, field_names=field_names)
        if mode in {'create', 'write'}:
            cls.sync_code(products)

    @classmethod
    def check_modification(cls, mode, products, values=None, external=False):
        super().check_modification(
            mode, products, values=values, external=external)
        if mode == 'write' and 'template' in values:
            for product in products:
                if product.template.id != values.get('template'):
                    raise AccessError(gettext(
                            'product.msg_product_change_template',
                            product=product.rec_name))

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('suffix_code', None)
        default.setdefault('code', None)
        default.setdefault('replaced_by')
        default.setdefault('replacing')
        return super().copy(products, default=default)

    def get_list_price_used(self, name):
        list_price = self.get_multivalue('list_price')
        if list_price is None:
            list_price = self.template.get_multivalue('list_price')
        return list_price

    @classmethod
    def sync_code(cls, products):
        for product in products:
            code = ''.join(filter(None, [
                        product.prefix_code, product.suffix_code]))
            if cls.code.strip:
                if cls.code.strip == 'leading':
                    code = code.lstrip()
                elif cls.code.strip == 'trailing':
                    code = code.rstrip()
                else:
                    code = code.strip()
            if not code:
                code = None
            if code != product.code:
                product.code = code
        cls.save(products)

    def can_be_deactivated(self):
        return True

    @classmethod
    def deactivate_replaced(cls, products=None):
        if products is None:
            products = cls.search([
                    ('replaced_by', '!=', None),
                    ('active', '=', True),
                    ])
        deactivated = []
        for product in products:
            if product.can_be_deactivated():
                deactivated.append(product)
        if deactivated:
            cls.write(deactivated, {'active': False})
        return deactivated

    @property
    def replacement(self):
        replacement = self
        while replacement.replaced_by and not replacement.active:
            replacement = replacement.replaced_by
        return replacement


class ProductListPrice(ModelSQL, CompanyValueMixin):
    __name__ = 'product.list_price'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', required=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE',
        domain=[
            ('template', '=', Eval('template', -1)),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    list_price = fields.Numeric("List Price", digits=price_digits)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.company.required = True


class ProductCostPriceMethod(ModelSQL, CompanyValueMixin):
    __name__ = 'product.cost_price_method'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    cost_price_method = fields.Selection(
        'get_cost_price_methods', "Cost Price Method")

    @classmethod
    def get_cost_price_methods(cls):
        pool = Pool()
        Template = pool.get('product.template')
        field_name = 'cost_price_method'
        methods = Template.fields_get([field_name])[field_name]['selection']
        methods.append((None, ''))
        return methods


class ProductCostPrice(ModelSQL, CompanyValueMixin):
    __name__ = 'product.cost_price'
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    cost_price = fields.Numeric(
        "Cost Price", required=True, digits=price_digits)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.company.required = True


class TemplateCategory(ModelSQL):
    __name__ = 'product.template-product.category'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', required=True)
    category = fields.Many2One(
        'product.category', "Category", ondelete='CASCADE', required=True)


class TemplateCategoryAll(UnionMixin, ModelSQL):
    __name__ = 'product.template-product.category.all'
    template = fields.Many2One('product.template', "Template")
    category = fields.Many2One('product.category', "Category")

    @classmethod
    def union_models(cls):
        return ['product.template-product.category']


class ProductIdentifier(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'product.identifier'
    _rec_name = 'code'
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE', required=True,
        help="The product identified by the code.")
    type = fields.Selection([
            (None, ''),
            ('ean', "International Article Number"),
            ('isan', "International Standard Audiovisual Number"),
            ('isbn', "International Standard Book Number"),
            ('isil', "International Standard Identifier for Libraries"),
            ('isin', "International Securities Identification Number"),
            ('ismn', "International Standard Music Number"),
            ('brand', "Brand"),
            ('mpn', "Manufacturer Part Number"),
            ], "Type")
    type_string = type.translated('type')
    code = fields.Char("Code", required=True)

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        cls.__access__.add('product')
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t,
                    (t.product, Index.Range()),
                    (t.code, Index.Similarity(cardinality='high'))),
                })

    @property
    @fields.depends('type')
    def _is_stdnum(self):
        return self.type in {'ean', 'isan', 'isbn', 'isil', 'isin', 'ismn'}

    @fields.depends('type', 'code', methods=['_is_stdnum'])
    def on_change_with_code(self):
        if self._is_stdnum:
            try:
                module = import_module('stdnum.%s' % self.type)
                return module.compact(self.code)
            except ImportError:
                pass
            except stdnum.exceptions.ValidationError:
                pass
        return self.code

    def pre_validate(self):
        super().pre_validate()
        self.check_code()

    @fields.depends('type', 'product', 'code', methods=['_is_stdnum'])
    def check_code(self):
        if self._is_stdnum:
            try:
                module = import_module('stdnum.%s' % self.type)
            except ModuleNotFoundError:
                return
            if not module.is_valid(self.code):
                if self.product and self.product.id > 0:
                    product = self.product.rec_name
                else:
                    product = ''
                raise InvalidIdentifierCode(
                    gettext('product.msg_invalid_code',
                        type=self.type_string,
                        code=self.code,
                        product=product))

    def barcode(self, format='svg', type=None, **options):
        if type is None:
            type = self.type
        if barcode and type in barcode.BARCODES:
            generator = getattr(barcode, 'generate_%s' % format)
            return generator(type, self.on_change_with_code(), **options)


class ProductReplace(Wizard):
    __name__ = 'product.product.replace'
    start_state = 'ask'
    ask = StateView(
        'product.product.replace.ask', 'product.product_replace_ask_view_form',
        [Button("Cancel", 'end', 'tryton-cancel'),
            Button("Replace", 'replace', 'tryton-launch', default=True),
            ])
    replace = StateTransition()

    def transition_replace(self):
        source = self.ask.source
        destination = self.ask.destination

        source.replaced_by = destination
        source.save()
        self.model.deactivate_replaced([source])
        return 'end'


class ProductReplaceAsk(ModelView):
    __name__ = 'product.product.replace.ask'
    source = fields.Many2One(
        'product.product', "Source", required=True,
        domain=[
            ('replaced_by', '=', None),
            ],
        help="The product to be replaced.")
    destination = fields.Many2One(
        'product.product', "Destination", required=True,
        domain=[
            ('id', '!=', Eval('source', -1)),
            ('type', '=', Eval('source_type')),
            ('default_uom_category',
                '=', Eval('source_default_uom_category', -1)),
            ],
        help="The product that replaces.")

    source_type = fields.Function(fields.Selection('get_types', "Source Type"),
        'on_change_with_source_type')
    source_default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Source Default UoM Category"),
        'on_change_with_source_default_uom_category')

    @classmethod
    def default_source(cls):
        context = Transaction().context
        if context.get('active_model') == 'product.product':
            return context.get('active_id')

    @fields.depends('source')
    def on_change_source(self):
        if self.source and self.source.replaced_by:
            self.destination = self.source.replaced_by

    @classmethod
    def get_types(cls):
        pool = Pool()
        Product = pool.get('product.product')
        return Product.fields_get(['type'])['type']['selection']

    @fields.depends('source')
    def on_change_with_source_type(self):
        if self.source:
            return self.source.type

    @fields.depends('source')
    def on_change_with_source_default_uom_category(self):
        if self.source:
            return self.source.default_uom_category
