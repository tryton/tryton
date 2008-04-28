from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}


class Template(OSV):
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
            type="numeric", digits=(16, 4))
    cost_price_method = fields.Selection([
        ("fixed", "Fixed"),
        ("average", "Average")
        ], "Cost Method", required=True)
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
            states=STATES)
    active = fields.Boolean('Active')

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
                        to_uom)
        else:
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = product[field]
        return res

Template()
