#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
import datetime

class Product(OSV):
    "Product"
    _name = "product.product"

    order_points = fields.One2Many(
        'supply.order_point', 'product', 'Order Points')

Product()

class ProductSupplier(OSV):
    'Product Supplier'
    _name = 'purchase.product_supplier'

    lead_time = fields.Integer("Lead Time") # XXX put it on the party obj ?

ProductSupplier()
