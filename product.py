from trytond.osv import fields, OSV

class Product(OSV):
    "Product"
    _name = "product.product"
    _description = __doc__
    _inherits = {'product.template': 'product_template'}

    product_template = fields.Many2One('product.template', 'Product Template',
                                        required=True)

Product()
