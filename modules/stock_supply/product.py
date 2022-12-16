# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import fields
from trytond.pool import PoolMeta, Pool

__all__ = ['Product', 'ProductSupplier']


class Product(metaclass=PoolMeta):
    __name__ = "product.product"
    order_points = fields.One2Many(
        'stock.order_point', 'product', 'Order Points')


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'

    def get_supply_period(self, **pattern):
        'Return the supply period for the purchase request'
        pool = Pool()
        Configuration = pool.get('purchase.configuration')
        config = Configuration(1)
        supply_period = config.get_multivalue('supply_period', **pattern)
        return supply_period or datetime.timedelta(1)
