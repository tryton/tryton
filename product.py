#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']


class Template(ModelSQL, ModelView):
    "Product Template"
    _name = "product.template"
    _description = __doc__

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
        'get_default_uom_category')
    active = fields.Boolean('Active', select=True)
    products = fields.One2Many('product.product', 'template', 'Products',
        states=STATES, depends=DEPENDS)

    def init(self, module_name):
        cursor = Transaction().cursor

        super(Template, self).init(module_name)

        table = TableHandler(cursor, self, module_name)
        # Migration from 2.2: category is no more required
        table.not_null_action('category', 'remove')

        # Migration from 2.2: new types
        cursor.execute('UPDATE "' + self._table + '" '
            'SET consumable = %s WHERE type = %s', (True, 'consumable'))
        cursor.execute('UPDATE "' + self._table + '" '
            'SET type = %s WHERE type IN (%s, %s)',
            ('goods', 'stockable', 'consumable'))

    def default_active(self):
        return True

    def default_type(self):
        return 'goods'

    def default_cost_price_method(self):
        return 'fixed'

    def on_change_with_default_uom_category(self, values):
        pool = Pool()
        uom_obj = pool.get('product.uom')
        if values.get('default_uom'):
            uom = uom_obj.browse(values['default_uom'])
            return uom.category.id

    def get_default_uom_category(self, ids, name):
        categories = {}
        for template in self.browse(ids):
            categories[template.id] = template.default_uom.category.id
        return categories

    def get_price_uom(self, ids, name):
        product_uom_obj = Pool().get('product.uom')
        res = {}
        field = name[:-4]
        if Transaction().context.get('uom'):
            to_uom = product_uom_obj.browse(
                Transaction().context['uom'])
            for product in self.browse(ids):
                res[product.id] = product_uom_obj.compute_price(
                        product.default_uom, product[field], to_uom)
        else:
            for product in self.browse(ids):
                res[product.id] = product[field]
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = None
        return super(Template, self).copy(ids, default=default)

Template()


class Product(ModelSQL, ModelView):
    "Product"
    _name = "product.product"
    _description = __doc__
    _inherits = {'product.template': 'template'}

    template = fields.Many2One('product.template', 'Product Template',
            required=True, ondelete='CASCADE', select=True)
    code = fields.Char("Code", size=None, select=True)
    description = fields.Text("Description", translate=True)

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for product in self.browse(ids):
            name = product.name
            if product.code:
                name = '[' + product.code + '] ' + product.name
            res[product.id] = name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], order=[])
        if ids:
            ids += self.search([('name',) + clause[1:]], order=[])
            return [('id', 'in', ids)]
        return [('name',) + clause[1:]]

    def delete(self, ids):
        template_obj = Pool().get('product.template')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Get the templates before we delete the products.
        products = self.browse(ids)
        template_ids = [product.template.id for product in products]

        res = super(Product, self).delete(ids)

        # Get templates that are still linked after delete.
        templates = template_obj.browse(template_ids)
        unlinked_template_ids = [template.id for template in templates \
                                 if not template.products]
        if unlinked_template_ids:
            template_obj.delete(unlinked_template_ids)

        return res

    def copy(self, ids, default=None):
        template_obj = Pool().get('product.template')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = None
        new_ids = []
        for product in self.browse(ids):
            default['template'] = template_obj.copy(product.template.id)
            new_id = super(Product, self).copy(product.id, default=default)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

Product()
