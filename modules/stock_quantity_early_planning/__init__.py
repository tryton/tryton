# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import stock

__all__ = ['register']


def register():
    Pool.register(
        stock.QuantityEarlyPlan,
        stock.Move,
        stock.QuantityEarlyPlanGenerateStart,
        module='stock_quantity_early_planning', type_='model')
    Pool.register(
        stock.QuantityEarlyPlanGenerate,
        module='stock_quantity_early_planning', type_='wizard')
    Pool.register(
        stock.QuantityEarlyPlanProduction,
        module='stock_quantity_early_planning', type_='model',
        depends=['production'])
