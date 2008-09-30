#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.osv import fields, OSV


class Product(OSV):
    _name = 'product.product'

    locations = fields.One2Many('stock.product.location', 'product',
            'Locations')

Product()
