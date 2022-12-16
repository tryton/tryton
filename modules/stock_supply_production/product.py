#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import Model
from trytond.pool import Pool


class Product(Model):
    _name = 'product.product'

    def get_supply_period(self, product):
        'Return the supply period for the product'
        pool = Pool()
        configuration_obj = pool.get('production.configuration')
        return int(configuration_obj.browse(1).supply_period or 0)

Product()
