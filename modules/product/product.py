#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Bool, Eval

STATES = {
    'readonly': Not(Bool(Eval('active'))),
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
    list_price = fields.Property(fields.Numeric('List Price', states=STATES,
        digits=(16, 4)))
    list_price_uom = fields.Function(fields.Numeric('List Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price = fields.Property(fields.Numeric('Cost Price',
            states=STATES, digits=(16, 4)))
    cost_price_uom = fields.Function(fields.Numeric('Cost Price',
        digits=(16, 4)), 'get_price_uom')
    cost_price_method = fields.Property(fields.Selection([
        ("fixed", "Fixed"),
        ("average", "Average")
        ], 'Cost Method', required=True, states=STATES))
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
            states=STATES)
    active = fields.Boolean('Active', select=1)
    products = fields.One2Many('product.product', 'template', 'Products',
            states=STATES)

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'stockable'

    def default_cost_price_method(self, cursor, user, context=None):
        return 'fixed'

    def get_price_uom(self, cursor, user, ids, name, context=None):
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

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = False
        return super(Template, self).copy(cursor, user, ids, default=default,
                context=context)

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

    def get_rec_name(self, cursor, user, ids, name, context=None):
        if not ids:
            return {}
        res = {}
        for product in self.browse(cursor, user, ids, context=context):
            name = product.name
            if product.code:
                name = '[' + product.code + '] ' + product.name
            res[product.id] = name
        return res

    def search_rec_name(self, cursor, user, name, clause, context=None):
        ids = self.search(cursor, user, [('code',) + clause[1:]],
                order=[], context=context)
        if ids:
            ids += self.search(cursor, user, [('name',) + clause[1:]],
                    order=[], context=context)
            return [('id', 'in', ids)]
        return [('name',) + clause[1:]]

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
        template_obj = self.pool.get('product.template')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        if default is None:
            default = {}
        default = default.copy()
        default['products'] = False
        new_ids = []
        for product in self.browse(cursor, user, ids, context=context):
            default['template'] = template_obj.copy(cursor, user,
                    product.template.id, context=context)
            new_id = super(Product, self).copy(cursor, user, product.id,
                default=default, context=context)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

Product()
