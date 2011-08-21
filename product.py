#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool

STATES = {
    'readonly': ~Eval('active', True),
    }
DEPENDS = ['active']


class Template(ModelSQL, ModelView):
    "Product Template"
    _name = "product.template"
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
        select=1, states=STATES, depends=DEPENDS)
    type = fields.Selection([
            ('stockable', 'Stockable'),
            ('consumable', 'Consumable'),
            ('service', 'Service')
            ], 'Type', required=True, states=STATES, depends=DEPENDS)
    category = fields.Many2One('product.category', 'Category', required=True,
        states=STATES, depends=DEPENDS)
    list_price = fields.Property(fields.Numeric('List Price', states=STATES,
            digits=(16, 4), depends=DEPENDS))
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price = fields.Property(fields.Numeric('Cost Price',
            states=STATES, digits=(16, 4), depends=DEPENDS))
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price_method = fields.Property(fields.Selection([
                ("fixed", "Fixed"),
                ("average", "Average")
                ], 'Cost Method', required=True, states=STATES,
            depends=DEPENDS))
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
        states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active', select=1)
    products = fields.One2Many('product.product', 'template', 'Products',
        states=STATES, depends=DEPENDS)

    def default_active(self):
        return True

    def default_type(self):
        return 'stockable'

    def default_cost_price_method(self):
        return 'fixed'

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
        default['products'] = False
        return super(Template, self).copy(ids, default=default)

Template()


class Product(ModelSQL, ModelView):
    "Product"
    _name = "product.product"
    _description = __doc__
    _inherits = {'product.template': 'template'}

    template = fields.Many2One('product.template', 'Product Template',
            required=True, ondelete='CASCADE', select=1)
    code = fields.Char("Code", size=None, select=1)
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
        default['products'] = False
        new_ids = []
        for product in self.browse(ids):
            default['template'] = template_obj.copy(product.template.id)
            new_id = super(Product, self).copy(product.id, default=default)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

Product()
