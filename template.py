from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}

class ProductTemplate(OSV):
    "Product Template"
    _name = "product.template"
    _description = __doc__


    name = fields.Char('Name', size=64, required=True, translate=True,
                       select=True, states=STATES,)
    type = fields.Selection([('product','Stockable Product'),
                             ('consu', 'Consumable'),('service','Service')],
                            'Product Type', required=True, states=STATES,)
    category = fields.Many2One('product.category','Category', required=True,
                               states=STATES,)
    list_price = fields.Numeric('List Price', digits=(12, 6), states=STATES,) #XXX digit ?
    default_uom = fields.Many2One('product.uom', 'Default UOM', required=True,
                                  states=STATES,)
    active = fields.Boolean('Active',)

    def default_active(self, cursor, user, context=None):
        return 1

ProductTemplate()
