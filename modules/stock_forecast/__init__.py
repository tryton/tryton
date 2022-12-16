#This file is part of Tryton.  The COPYRIGHT file at the top level of this
#repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .forecast import *


def register():
    Pool.register(
        Forecast,
        ForecastLine,
        ForecastLineMove,
        ForecastCompleteAsk,
        ForecastCompleteChoose,
        module='stock_forecast', type_='model')
    Pool.register(
        ForecastComplete,
        module='stock_forecast', type_='wizard')
