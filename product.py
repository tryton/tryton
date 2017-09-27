# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import logging

from trytond.model import ModelView, ModelSQL, Model, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
from trytond.config import config
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = ['Template', 'Product', 'price_digits', 'TemplateFunction',
    'ProductListPrice', 'ProductCostPrice', 'TemplateCategory']
logger = logging.getLogger(__name__)

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']
TYPES = [
    ('goods', 'Goods'),
    ('assets', 'Assets'),
    ('service', 'Service'),
    ]
COST_PRICE_METHODS = [
    ('fixed', 'Fixed'),
    ('average', 'Average'),
    ]

price_digits = (16, config.getint('product', 'price_decimal', default=4))


class Template(ModelSQL, ModelView, CompanyMultiValueMixin):
    "Product Template"
    __name__ = "product.template"
    name = fields.Char('Name', size=None, required=True, translate=True,
        select=True, states=STATES, depends=DEPENDS)
    type = fields.Selection(TYPES, 'Type', required=True, states=STATES,
        depends=DEPENDS)
    consumable = fields.Boolean('Consumable',
        states={
            'readonly': ~Eval('active', True),
            'invisible': Eval('type', 'goods') != 'goods',
            },
        depends=['active', 'type'])
    list_price = fields.MultiValue(fields.Numeric(
            "List Price", required=True, digits=price_digits,
            states=STATES, depends=DEPENDS))
    list_prices = fields.One2Many(
        'product.list_price', 'template', "List Prices")
    cost_price = fields.MultiValue(fields.Numeric(
            "Cost Price", required=True, digits=price_digits,
            states=STATES, depends=DEPENDS))
    cost_price_method = fields.MultiValue(fields.Selection(
            COST_PRICE_METHODS, "Cost Method", required=True,
            states=STATES, depends=DEPENDS))
    cost_prices = fields.One2Many(
        'product.cost_price', 'template', "Cost Prices")
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
        states=STATES, depends=DEPENDS)
    default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Default UOM Category'),
        'on_change_with_default_uom_category',
        searcher='search_default_uom_category')
    active = fields.Boolean('Active', select=True)
    categories = fields.Many2Many('product.template-product.category',
        'template', 'category', 'Categories', states=STATES, depends=DEPENDS)
    products = fields.One2Many('product.product', 'template', 'Variants',
        states=STATES, depends=DEPENDS)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Template, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        # Migration from 2.2: category is no more required
        table.not_null_action('category', 'remove')

        # Migration from 2.2: new types
        cursor.execute(*sql_table.update(
                columns=[sql_table.consumable],
                values=[True],
                where=sql_table.type == 'consumable'))
        cursor.execute(*sql_table.update(
                columns=[sql_table.type],
                values=['goods'],
                where=sql_table.type.in_(['stockable', 'consumable'])))

        # Migration from 3.8: rename category into categories
        if table.column_exist('category'):
            logger.warning(
                'The column "category" on table "%s" must be dropped manually',
                cls._table)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'list_price':
            return pool.get('product.list_price')
        elif field in {'cost_price', 'cost_price_method'}:
            return pool.get('product.cost_price')
        return super(Template, cls).multivalue_model(field)

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_type():
        return 'goods'

    @staticmethod
    def default_consumable():
        return False

    @classmethod
    def default_cost_price_method(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        return Configuration(1).get_multivalue(
            'default_cost_price_method', **pattern)

    @staticmethod
    def default_products():
        if Transaction().user == 0:
            return []
        return [{}]

    @fields.depends('default_uom')
    def on_change_with_default_uom_category(self, name=None):
        if self.default_uom:
            return self.default_uom.category.id

    @classmethod
    def search_default_uom_category(cls, name, clause):
        return [('default_uom.category' + clause[0].lstrip(name),)
            + tuple(clause[1:])]

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            values.setdefault('products', None)
        return super(Template, cls).create(vlist)

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
            else:
                template = tables['template']
            return getattr(Template, name).convert_order(
                name, tables['template'], Template)
        return order


class Product(ModelSQL, ModelView):
    "Product Variant"
    __name__ = "product.product"
    _order_name = 'rec_name'
    template = fields.Many2One('product.template', 'Product Template',
        required=True, ondelete='CASCADE', select=True, states=STATES,
        depends=DEPENDS)
    code = fields.Char("Code", size=None, select=True, states=STATES,
        depends=DEPENDS)
    description = fields.Text("Description", translate=True, states=STATES,
        depends=DEPENDS)
    active = fields.Boolean('Active', select=True)
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

        for attr in dir(Template):
            tfield = getattr(Template, attr)
            if not isinstance(tfield, fields.Field):
                continue
            if attr in cls._no_template_field:
                continue
            field = getattr(cls, attr, None)
            if not field or isinstance(field, TemplateFunction):
                setattr(cls, attr, TemplateFunction(copy.deepcopy(tfield)))
                order_method = getattr(cls, 'order_%s' % attr, None)
                if (not order_method
                        and not isinstance(tfield, (
                                fields.Function,
                                fields.One2Many,
                                fields.Many2Many))):
                    order_method = TemplateFunction.order(attr)
                    setattr(cls, 'order_%s' % attr, order_method)

    @fields.depends('template')
    def on_change_template(self):
        for name, field in self._fields.iteritems():
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

    @staticmethod
    def default_active():
        return True

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
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            ('template.name',) + tuple(clause[1:]),
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


class ProductListPrice(ModelSQL, CompanyValueMixin):
    "Product List Price"
    __name__ = 'product.list_price'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', select=True)
    list_price = fields.Numeric("List Price", digits=price_digits)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

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


class ProductCostPrice(ModelSQL, CompanyValueMixin):
    "Product Cost Price"
    __name__ = 'product.cost_price'
    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE', select=True)
    cost_price = fields.Numeric(
        "Cost Price", digits=price_digits)
    cost_price_method = fields.Selection(
        'get_cost_price_methods', "Cost Method")

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ProductCostPrice, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['cost_price', 'cost_price_method'])
        value_names.extend(['cost_price', 'cost_price_method'])
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


class TemplateCategory(ModelSQL):
    'Template - Category'
    __name__ = 'product.template-product.category'
    template = fields.Many2One('product.template', 'Template',
        ondelete='CASCADE', required=True, select=True)
    category = fields.Many2One('product.category', 'Category',
        ondelete='CASCADE', required=True, select=True)
