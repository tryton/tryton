# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool

__all__ = ['Product', 'ProductSupplier']


class Product:
    __metaclass__ = PoolMeta
    __name__ = "product.product"
    order_points = fields.One2Many(
        'stock.order_point', 'product', 'Order Points')


class ProductSupplier:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.product_supplier'

    def get_supply_period(self):
        'Return the supply period for the purchase request in days'
        pool = Pool()
        Configuration = pool.get('purchase.configuration')
        return Configuration(1).supply_period or 1
