#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields

STATES = {
    'readonly': "active == False",
}


class Template(ModelSQL, ModelView):
    "Product Template"
    _name = "product.template"
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1, states=STATES)
    type = fields.Selection([
        ('stockable', 'Stockable'),
        ('consumable', 'Consumable'),
        ('service', 'Service')
        ], 'Type', required=True, states=STATES)
    category = fields.Many2One('product.category','Category', required=True,
            states=STATES)
    list_price = fields.Property(type='numeric', string='List Price',
            states=STATES, digits=(16, 4))
    list_price_uom = fields.Function('get_price_uom', string='List Price',
            type="numeric", digits=(16, 4))
    cost_price = fields.Property(type='numeric', string='Cost Price',
            states=STATES, digits=(16, 4))
    cost_price_uom = fields.Function('get_price_uom', string='Cost Price',
            type="numeric", digits=(16, 4), states=STATES)
    cost_price_method = fields.Property(type='selection', selection=[
        ("fixed", "Fixed"),
        ("average", "Average")
        ], string="Cost Method", required=True, states=STATES)
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
            states=STATES)
    active = fields.Boolean('Active')
    products = fields.One2Many('product.product', 'template', 'Products',
            states=STATES)

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'stockable'

    def default_cost_price_method(self, cursor, user, context=None):
        return 'fixed'

    def get_price_uom(self, cursor, user, ids, name, arg, context=None):
        product_uom_obj = self.pool.get('product.uom')
        res = {}
        if context is None:
            context = {}
        field = name[:-4]
        if context.get('uom'):
            to_uom = self.pool.get('product.uom').browse(
                cursor, user, context['uom'], context=context)
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = product_uom_obj.compute_price(
                        cursor, user, product.default_uom, product[field],
                        to_uom, context=context)
        else:
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = product[field]
        return res

Template()


class Product(ModelSQL, ModelView):
    "Product"
    _name = "product.product"
    _description = __doc__
    _inherits = {'product.template': 'template'}

    template = fields.Many2One('product.template', 'Product Template',
            required=True, ondelete='CASCADE')
    code = fields.Char("Code", size=None)
    description = fields.Text("Description", translate=True)

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return {}
        res = {}
        for product in self.browse(cursor, user, ids, context=context):
            name = product.name
            if product.code:
                name = '[' + product.code + '] ' + product.name
            res[product.id] = name
        return res

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search(cursor, user, [('code', args[i][1], args[i][2])],
                    context=context)
            if ids:
                args2.append(('id', 'in', ids))
            else:
                args2.append(('name', args[i][1], args[i][2]))
            i += 1
        return args2

    def delete(self, cursor, user, ids, context=None):
        template_obj = self.pool.get('product.template')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Get the templates before we delete the products.
        products = self.browse(cursor, user, ids, context=context)
        template_ids = [product.template.id for product in products]

        res = super(Product, self).delete(cursor, user, ids, context=context)

        # Get templates that are still linked after delete.
        templates = template_obj.browse(cursor, user, template_ids,
                                        context=context)
        unlinked_template_ids = [template.id for template in templates \
                                 if not template.products]
        if unlinked_template_ids:
            template_obj.delete(cursor, user, unlinked_template_ids,
                                context=context)

        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = False
        return super(Product, self).copy(cursor, user, ids,
                default=default, context=context)

Product()
