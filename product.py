# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import logging
from decimal import Decimal
from importlib import import_module

import stdnum
import stdnum.exceptions
from sql import Null, Column, Literal
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, Model, UnionMixin, DeactivableMixin, sequence_ordered,
    Exclude, fields)
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
from trytond.tools import lstrip_wildcard
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
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

price_digits = (16, price_decimal)


def round_price(value, rounding=None):
    "Round price using the price digits"
    return value.quantize(
        Decimal(1) / 10 ** price_digits[1], rounding=rounding)


class Template(
        DeactivableMixin, ModelSQL, ModelView, CompanyMultiValueMixin):
    "Product Template"
    __name__ = "product.template"
    _order_name = 'rec_name'
    name = fields.Char(
        "Name", size=None, required=True, translate=True, select=True)
    code_readonly = fields.Function(
        fields.Boolean("Code Readonly"), 'get_code_readonly')
    code = fields.Char(
        "Code", select=True,
        states={
            'readonly': Eval('code_readonly', False),
            },
        depends=['code_readonly'])
    type = fields.Selection(TYPES, "Type", required=True)
    consumable = fields.Boolean('Consumable',
        states={
            'invisible': Eval('type', 'goods') != 'goods',
            },
        depends=['type'],
        help="Check to allow stock moves to be assigned "
        "regardless of stock level.")
    list_price = fields.MultiValue(fields.Numeric(
            "List Price", required=True, digits=price_digits,
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
    default_uom = fields.Many2One('product.uom', "Default UOM", required=True,
        help="The standard unit of measure for the product.\n"
        "Used internally when calculating the stock levels of goods "
        "and assets.")
    default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Default UOM Category'),
        'on_change_with_default_uom_category',
        searcher='search_default_uom_category')
    default_uom_digits = fields.Function(fields.Integer("Default Unit Digits"),
        'on_change_with_default_uom_digits')
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
        domain=[
            If(~Eval('active'), ('active', '=', False), ()),
            ],
        depends=['active'],
        help="The different variants the product comes in.")

    @classmethod
    def __register__(cls, module_name):
        super(Template, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 3.8: rename category into categories
        if table.column_exist('category'):
            logger.warning(
                'The column "category" on table "%s" must be dropped manually',
                cls._table)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('rec_name', 'ASC'))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'list_price':
            return pool.get('product.list_price')
        elif field == 'cost_price_method':
            return pool.get('product.cost_price_method')
        return super(Template, cls).multivalue_model(field)

    @classmethod
    def order_rec_name(cls, tables):
        table, _ = tables[None]
        return [table.code, table.name]

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('name',) + tuple(clause[1:]),
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ('products.code', clause[1], code_value) + tuple(clause[3:]),
            ('products.identifiers.code', clause[1], code_value)
            + tuple(clause[3:]),
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
        if self.default_uom:
            return self.default_uom.category.id

    @classmethod
    def search_default_uom_category(cls, name, clause):
        return [('default_uom.category' + clause[0].lstrip(name),)
            + tuple(clause[1:])]

    @fields.depends('default_uom')
    def on_change_with_default_uom_digits(self, name=None):
        if self.default_uom:
            return self.default_uom.digits

    @classmethod
    def _new_code(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        sequence = config.template_sequence
        if sequence:
            return sequence.get()

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Product = pool.get('product.product')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            values.setdefault('products', None)
            if not values.get('code'):
                values['code'] = cls._new_code()
        templates = super(Template, cls).create(vlist)
        products = sum((t.products for t in templates), ())
        Product.sync_code(products)
        return templates

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Product = pool.get('product.product')
        super().write(*args)
        templates = sum(args[0:None:2], [])
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
        for record, rec_name, icon in super(Template, cls).search_global(text):
            icon = icon or 'tryton-product'
            yield record, rec_name, icon


class TemplateFunction(fields.Function):

    def __init__(self, field):
        super(TemplateFunction, self).__init__(
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

    def definition(self, model, language):
        pool = Pool()
        Template = pool.get('product.template')
        definition = super().definition(model, language)
        definition['searchable'] = self._field.definition(
            Template, language)['searchable']
        return definition


class Product(
        DeactivableMixin, ModelSQL, ModelView, CompanyMultiValueMixin):
    "Product Variant"
    __name__ = "product.product"
    _order_name = 'rec_name'
    template = fields.Many2One(
        'product.template', "Product Template",
        required=True, ondelete='CASCADE', select=True,
        search_context={'default_products': False},
        domain=[
            If(Eval('active'), ('active', '=', True), ()),
            ],
        depends=['active'],
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
        "Suffix Code",
        states={
            'readonly': Eval('code_readonly', False),
            },
        depends=['code_readonly'],
        help="The unique identifier for the product (aka SKU).")
    code = fields.Char("Code", readonly=True, select=True,
        help="A unique identifier for the variant.")
    identifiers = fields.One2Many(
        'product.identifier', 'product', "Identifiers",
        help="Other identifiers associated with the variant.")
    cost_price = fields.MultiValue(fields.Numeric(
            "Cost Price", required=True, digits=price_digits,
            help="The amount it costs to purchase or make the variant, "
            "or carry out the service."))
    cost_prices = fields.One2Many(
        'product.cost_price', 'product', "Cost Prices")
    description = fields.Text("Description", translate=True)
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=price_digits), 'get_price_uom')
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=price_digits), 'get_price_uom')

    @classmethod
    def __setup__(cls):
        pool = Pool()
        Template = pool.get('product.template')

        if not hasattr(cls, '_no_template_field'):
            cls._no_template_field = set()
        cls._no_template_field.update(['products'])

        super(Product, cls).__setup__()
        cls.__access__.add('template')
        cls._order.insert(0, ('rec_name', 'ASC'))

        t = cls.__table__()
        cls._sql_constraints = [
            ('code_exclude', Exclude(t, (t.code, Equal),
                    where=(t.active == Literal(True))
                    & (t.code != '')),
                'product.msg_product_code_unique'),
            ]

        for attr in dir(Template):
            tfield = getattr(Template, attr)
            if not isinstance(tfield, fields.Field):
                continue
            if attr in cls._no_template_field:
                continue
            field = getattr(cls, attr, None)
            if not field or isinstance(field, TemplateFunction):
                tfield = copy.deepcopy(tfield)
                if hasattr(tfield, 'field'):
                    tfield.field = None
                invisible_state = ~Eval('template')
                if 'invisible' in tfield.states:
                    tfield.states['invisible'] |= invisible_state
                else:
                    tfield.states['invisible'] = invisible_state
                if 'template' not in tfield.depends:
                    tfield.depends.append('template')
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
    def __register__(cls, module):
        table = cls.__table__()
        table_h = cls.__table_handler__(module)
        fill_suffix_code = (
            table_h.column_exist('code')
            and not table_h.column_exist('suffix_code'))
        super().__register__(module)
        cursor = Transaction().connection.cursor()

        # Migration from 5.4: split code into prefix/suffix
        if fill_suffix_code:
            cursor.execute(*table.update(
                    [table.suffix_code],
                    [table.code]))

    @classmethod
    def _set_template_function(cls, products, name, value):
        # Prevent NotImplementedError for One2Many
        pass

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
        if field == 'cost_price':
            return pool.get('product.cost_price')
        return super(Product, cls).multivalue_model(field)

    @classmethod
    def default_cost_price(cls, **pattern):
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
        else:
            template = tables['template']
        return [product.code] + Template.name.convert_order('name',
            tables['template'], Template)

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ('identifiers.code', clause[1], code_value) + tuple(clause[3:]),
            ('template.name',) + tuple(clause[1:]),
            ('template.code', clause[1], code_value) + tuple(clause[3:]),
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
        for id_, rec_name, icon in super(Product, cls).search_global(text):
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

    @classmethod
    def _new_suffix_code(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        sequence = config.product_sequence
        if sequence:
            return sequence.get()

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('suffix_code'):
                values['suffix_code'] = cls._new_suffix_code()
        products = super().create(vlist)
        cls.sync_code(products)
        return products

    @classmethod
    def write(cls, *args):
        super().write(*args)
        products = sum(args[0:None:2], [])
        cls.sync_code(products)

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('suffix_code', None)
        default.setdefault('code', None)
        return super().copy(products, default=default)

    @property
    def list_price_used(self):
        transaction = Transaction()
        with transaction.reset_context(), \
                transaction.set_context(self._context):
            return self.template.get_multivalue('list_price')

    @classmethod
    def sync_code(cls, products):
        for product in products:
            code = ''.join(filter(None, [
                        product.prefix_code, product.suffix_code]))
            if not code:
                code = None
            if code != product.code:
                product.code = code
        cls.save(products)


class ProductListPrice(ModelSQL, CompanyValueMixin):
    "Product List Price"
    __name__ = 'product.list_price'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    list_price = fields.Numeric("List Price", digits=price_digits)

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ProductListPrice, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('list_price')
        value_names.append('list_price')
        fields.append('company')
        migrate_property(
            'product.template', field_names, cls, value_names,
            parent='template', fields=fields)


class ProductCostPriceMethod(ModelSQL, CompanyValueMixin):
    "Product Cost Price Method"
    __name__ = 'product.cost_price_method'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    cost_price_method = fields.Selection(
        'get_cost_price_methods', "Cost Price Method")

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ProductCostPrice = pool.get('product.cost_price')
        sql_table = cls.__table__()
        cost_price = ProductCostPrice.__table__()
        cursor = Transaction().connection.cursor()

        exist = backend.TableHandler.table_exist(cls._table)
        cost_price_exist = backend.TableHandler.table_exist(
            ProductCostPrice._table)

        super(ProductCostPriceMethod, cls).__register__(module_name)

        # Migrate from 4.4: move cost_price_method from ProductCostPrice
        if not exist and not cost_price_exist:
            cls._migrate_property([], [], [])
        elif not exist and cost_price_exist:
            cost_price_table = backend.TableHandler(
                ProductCostPrice, module_name)
            if cost_price_table.column_exist('template'):
                columns = ['create_uid', 'create_date',
                    'write_uid', 'write_date',
                    'template', 'cost_price_method']
                cursor.execute(*sql_table.insert(
                        columns=[Column(sql_table, c) for c in columns],
                        values=cost_price.select(
                            *[Column(cost_price, c) for c in columns])))

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('cost_price_method')
        value_names.append('cost_price_method')
        fields.append('company')
        migrate_property(
            'product.template', field_names, cls, value_names,
            parent='template', fields=fields)

    @classmethod
    def get_cost_price_methods(cls):
        pool = Pool()
        Template = pool.get('product.template')
        field_name = 'cost_price_method'
        methods = Template.fields_get([field_name])[field_name]['selection']
        methods.append((None, ''))
        return methods


class ProductCostPrice(ModelSQL, CompanyValueMixin):
    "Product Cost Price"
    __name__ = 'product.cost_price'
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    cost_price = fields.Numeric(
        "Cost Price", digits=price_digits)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Product = pool.get('product.product')
        sql_table = cls.__table__()
        product = Product.__table__()
        cursor = Transaction().connection.cursor()

        exist = backend.TableHandler.table_exist(cls._table)

        super(ProductCostPrice, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        if not exist:
            # Create template column for property migration
            table.add_column('template', 'INTEGER')
            cls._migrate_property([], [], [])

        # Migration from 4.4: replace template by product
        if table.column_exist('template'):
            columns = ['create_uid', 'create_date',
                'write_uid', 'write_date', 'cost_price']
            cursor.execute(*sql_table.insert(
                    columns=[Column(sql_table, c) for c in columns]
                    + [sql_table.product],
                    values=sql_table.join(product,
                        condition=sql_table.template == product.template
                        ).select(
                        *[Column(sql_table, c) for c in columns]
                        + [product.id],
                        where=(sql_table.template != Null)
                        & (sql_table.product == Null))))
            cursor.execute(*sql_table.delete(
                    where=(sql_table.template != Null)
                    & (sql_table.product == Null)))
            table.drop_column('template')

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('cost_price')
        value_names.append('cost_price')
        fields.append('company')
        migrate_property(
            'product.template', field_names, cls, value_names,
            parent='template', fields=fields)


class TemplateCategory(ModelSQL):
    'Template - Category'
    __name__ = 'product.template-product.category'
    template = fields.Many2One('product.template', 'Template',
        ondelete='CASCADE', required=True, select=True)
    category = fields.Many2One('product.category', 'Category',
        ondelete='CASCADE', required=True, select=True)


class TemplateCategoryAll(UnionMixin, ModelSQL):
    "Template - Category All"
    __name__ = 'product.template-product.category.all'
    template = fields.Many2One('product.template', "Template")
    category = fields.Many2One('product.category', "Category")

    @classmethod
    def union_models(cls):
        return ['product.template-product.category']


class ProductIdentifier(sequence_ordered(), ModelSQL, ModelView):
    "Product Identifier"
    __name__ = 'product.identifier'
    _rec_name = 'code'
    product = fields.Many2One('product.product', "Product", ondelete='CASCADE',
        required=True, select=True,
        help="The product identified by the code.")
    type = fields.Selection([
            (None, ''),
            ('ean', "International Article Number"),
            ('isan', "International Standard Audiovisual Number"),
            ('isbn', "International Standard Book Number"),
            ('isil', "International Standard Identifier for Libraries"),
            ('isin', "International Securities Identification Number"),
            ('ismn', "International Standard Music Number"),
            ], "Type")
    type_string = type.translated('type')
    code = fields.Char("Code", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('product')

    @fields.depends('type', 'code')
    def on_change_with_code(self):
        if self.type and self.type != 'other':
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

    @fields.depends('type', 'product', 'code')
    def check_code(self):
        if self.type:
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
