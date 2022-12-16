# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


class Supply(metaclass=PoolMeta):
    __name__ = 'stock.supply'

    def transition_create_(self):
        pool = Pool()
        Forecast = pool.get('stock.forecast')
        Date = pool.get('ir.date')

        today = Date.today()

        forecasts = Forecast.search([
                ('to_date', '>=', today),
                ('state', '=', 'done'),
                ])
        Forecast.create_moves(forecasts)
        transition = super().transition_create_()
        Forecast.delete_moves(forecasts)
        return transition
