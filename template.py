from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}

class Template(OSV):
    "Product Template"
    _name = "product.template"
    _description = __doc__


    name = fields.Char('Name', size=64, required=True, translate=True,
                       select=True, states=STATES,)
    type = fields.Selection([('stockable','Stockable Product'),
                             ('consumable', 'Consumable'),('service','Service')],
                            'Type', required=True, states=STATES,)
    category = fields.Many2One('product.category','Category', required=True,
                               states=STATES,)
    list_price = fields.Numeric('List Price', states=STATES,)
    list_price_uom = fields.Function('get_list_price_uom', string='List Price',
                                      type="numeric", digits=(12, 2),)
    cost_price = fields.Numeric('Cost Price', states=STATES, digits=(12, 2))
    cost_price_method = fields.Selection(
        [("fixed","Fixed Price"),("average","Average Cost Price")],
        "Cost Method", required=True)
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
                                  states=STATES,)
    active = fields.Boolean('Active',)

    def default_active(self, cursor, user, context=None):
        return 1

    def default_type(self, cursor, user, context=None):
        return 'stockable'

    def default_cost_price_method(self, cursor, user, context=None):
        return 'fixed'

    def get_list_price_uom(self, cursor, user, ids, name, arg, context=None):
        product_uom_obj = self.pool.get('product.uom')
        res = {}
        if context and 'uom' in context:
            to_uom = self.pool.get('product.uom').browse(
                cursor, user, context['uom'], context=context)
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = product_uom_obj._compute_price(
                    cursor, user, product.default_uom, product.list_price,
                    to_uom)
        else:
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = product.list_price
        return res

Template()
