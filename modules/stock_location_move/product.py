# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = ['Product']


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    @classmethod
    def products_by_location(cls, *args, **kwargs):
        pool = Pool()
        Location = pool.get('stock.location')
        context = Transaction().context
        forecast_location_move = context.get('forecast_location_move', False)
        if forecast_location_move:
            date = context.get('stock_date_end') or datetime.date.max
            restore = Location.forecast_location_move(date)
        quantities = super(Product, cls).products_by_location(*args, **kwargs)
        if forecast_location_move:
            restore()
        return quantities
