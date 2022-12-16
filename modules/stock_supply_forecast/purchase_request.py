#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = ['PurchaseRequest']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def generate_requests(cls):
        pool = Pool()
        Forecast = pool.get('stock.forecast')
        Date = pool.get('ir.date')

        today = Date.today()

        forecasts = Forecast.search([
                ('to_date', '>=', today),
                ('state', '=', 'done'),
                ])
        Forecast.create_moves(forecasts)
        super(PurchaseRequest, cls).generate_requests()
        Forecast.delete_moves(forecasts)
