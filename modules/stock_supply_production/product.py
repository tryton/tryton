# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from datetime import timedelta

from trytond.pool import Pool, PoolMeta


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def get_supply_period(self):
        'Return the supply period for the product'
        pool = Pool()
        Configuration = pool.get('production.configuration')
        return Configuration(1).supply_period or timedelta(0)
