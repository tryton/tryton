#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler
from trytond.const import OPERATORS

__all__ = ['Template', 'Product']

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']
TYPES = [
    ('goods', 'Goods'),
    ('assets', 'Assets'),
    ('service', 'Service'),
    ]


class Template(ModelSQL, ModelView):
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
    category = fields.Many2One('product.category', 'Category',
        states=STATES, depends=DEPENDS)
    list_price = fields.Property(fields.Numeric('List Price', states=STATES,
            digits=(16, 4), depends=DEPENDS, required=True))
    cost_price = fields.Property(fields.Numeric('Cost Price',
            states=STATES, digits=(16, 4), depends=DEPENDS, required=True))
    cost_price_method = fields.Property(fields.Selection([
                ("fixed", "Fixed"),
                ("average", "Average")
                ], 'Cost Method', required=True, states=STATES,
            depends=DEPENDS))
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
        states=STATES, depends=DEPENDS)
    default_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Default UOM Category',
            on_change_with=['default_uom']),
        'on_change_with_default_uom_category')
    active = fields.Boolean('Active', select=True)
    products = fields.One2Many('product.product', 'template', 'Variants',
        states=STATES, depends=DEPENDS)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(Template, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.2: category is no more required
        table.not_null_action('category', 'remove')

        # Migration from 2.2: new types
        cursor.execute('UPDATE "' + cls._table + '" '
            'SET consumable = %s WHERE type = %s', (True, 'consumable'))
        cursor.execute('UPDATE "' + cls._table + '" '
            'SET type = %s WHERE type IN (%s, %s)',
            ('goods', 'stockable', 'consumable'))

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_type():
        return 'goods'

    @staticmethod
    def default_consumable():
        return False

    @staticmethod
    def default_cost_price_method():
        return 'fixed'

    @staticmethod
    def default_products():
        pool = Pool()
        Product = pool.get('product.product')
        if Transaction().user == 0:
            return []
        fields_names = list(f for f in Product._fields.keys()
            if f not in ('id', 'create_uid', 'create_date',
                'write_uid', 'write_date'))
        return [Product.default_get(fields_names)]

    def on_change_with_default_uom_category(self, name=None):
        if self.default_uom:
            return self.default_uom.category.id


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
    default_uom = fields.Function(fields.Many2One('product.uom',
            'Default UOM'), 'get_default_uom', searcher='search_default_uom')
    type = fields.Function(fields.Selection(TYPES, 'Type',
            on_change_with=['template']),
        'on_change_with_type', searcher='search_type')
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=(16, 4)), 'get_price_uom')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        # XXX order by id until order by joined name is possible
        # but at least products are grouped
        cls.rec_name.order_field = ("%(table)s.code %(order)s, "
            "%(table)s.id %(order)s")

    @staticmethod
    def default_active():
        return True

    def __getattr__(self, name):
        try:
            return super(Product, self).__getattr__(name)
        except AttributeError:
            pass
        return getattr(self.template, name)

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        ids = map(int, cls.search([('code',) + clause[1:]], order=[]))
        if ids:
            ids += map(int, cls.search([('template.name',) + clause[1:]],
                    order=[]))
            return [('id', 'in', ids)]
        return [('template.name',) + clause[1:]]

    def get_default_uom(self, name):
        return self.template.default_uom.id

    @classmethod
    def search_default_uom(cls, name, clause):
        return [('template.default_uom',) + tuple(clause[1:])]

    def on_change_with_type(self, name=None):
        if self.template:
            return self.template.type

    @classmethod
    def search_type(cls, name, clause):
        return [('template.type',) + tuple(clause[1:])]

    @staticmethod
    def get_price_uom(products, name):
        Uom = Pool().get('product.uom')
        res = {}
        field = name[:-4]
        if Transaction().context.get('uom'):
            to_uom = Uom(Transaction().context['uom'])
            for product in products:
                res[product.id] = Uom.compute_price(
                    product.default_uom, getattr(product, field), to_uom)
        else:
            for product in products:
                res[product.id] = getattr(product, field)
        return res

    @classmethod
    def search_domain(cls, domain, active_test=True):
        def convert_domain(domain):
            'Replace missing product field by the template one'
            if not domain:
                return []
            operator = 'AND'
            if isinstance(domain[0], basestring):
                operator = domain[0]
                domain = domain[1:]
            result = [operator]
            for arg in domain:
                if (isinstance(arg, (list, tuple))
                        and len(arg) > 2
                        and isinstance(arg[1], basestring)
                        and arg[1] in OPERATORS):
                    # clause
                    field = arg[0]
                    if not getattr(cls, field, None):
                        field = 'template.' + field
                    result.append((field,) + tuple(arg[1:]))
                elif isinstance(arg, list):
                    # sub-domain
                    result.append(convert_domain(arg))
                else:
                    result.append(arg)
            return result
        return super(Product, cls).search_domain(convert_domain(domain),
            active_test=active_test)
