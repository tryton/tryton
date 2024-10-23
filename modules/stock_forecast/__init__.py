# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import forecast, stock


def register():
    Pool.register(
        stock.Move,
        forecast.Forecast,
        forecast.ForecastLine,
        forecast.ForecastCompleteAsk,
        module='stock_forecast', type_='model')
    Pool.register(
        forecast.ForecastComplete,
        module='stock_forecast', type_='wizard')
