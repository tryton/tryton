#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    __name__ = 'product.product'

    def get_supply_period(self):
        'Return the supply period for the product'
        pool = Pool()
        Configuration = pool.get('production.configuration')
        return int(Configuration(1).supply_period or 0)
