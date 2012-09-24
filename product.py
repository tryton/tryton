#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler

__all__ = ['Template', 'Product']

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']


class Template(ModelSQL, ModelView):
    "Product Template"
    __name__ = "product.template"
    name = fields.Char('Name', size=None, required=True, translate=True,
        select=True, states=STATES, depends=DEPENDS)
    type = fields.Selection([
            ('goods', 'Goods'),
            ('assets', 'Assets'),
            ('service', 'Service')
            ], 'Type', required=True, states=STATES, depends=DEPENDS)
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
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price = fields.Property(fields.Numeric('Cost Price',
            states=STATES, digits=(16, 4), depends=DEPENDS, required=True))
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=(16, 4)), 'get_price_uom')
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
    products = fields.One2Many('product.product', 'template', 'Products',
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

    def on_change_with_default_uom_category(self, name=None):
        if self.default_uom:
            return self.default_uom.category.id

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
    def copy(cls, templates, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = None
        return super(Template, cls).copy(templates, default=default)


class Product(ModelSQL, ModelView):
    "Product"
    __name__ = "product.product"
    _inherits = {'product.template': 'template'}
    template = fields.Many2One('product.template', 'Product Template',
            required=True, ondelete='CASCADE', select=True)
    code = fields.Char("Code", size=None, select=True)
    description = fields.Text("Description", translate=True)

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        ids = map(int, cls.search([('code',) + clause[1:]], order=[]))
        if ids:
            ids += map(int, cls.search([('name',) + clause[1:]], order=[]))
            return [('id', 'in', ids)]
        return [('name',) + clause[1:]]

    @classmethod
    def delete(cls, products):
        Template = Pool().get('product.template')

        # Get the templates before we delete the products.
        templates = [product.template for product in products]

        super(Product, cls).delete(products)

        # Get templates that are still linked after delete.
        unlinked_templates = [template for template in templates
            if not template.products]
        if unlinked_templates:
            Template.delete(unlinked_templates)

    @classmethod
    def copy(cls, products, default=None):
        Template = Pool().get('product.template')

        if default is None:
            default = {}
        default = default.copy()
        default['products'] = None
        new_products = []
        for product in products:
            template, = Template.copy([product.template])
            default['template'] = template.id
            new_products.extend(super(Product, cls).copy([product],
                    default=default))
        return new_products
