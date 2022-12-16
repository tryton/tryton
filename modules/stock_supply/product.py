#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
import datetime


class Product(OSV):
    _name = "product.product"

    order_points = fields.One2Many(
        'stock.order_point', 'product', 'Order Points')

Product()
