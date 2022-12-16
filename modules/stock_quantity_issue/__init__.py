# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

__all__ = ['register']

from . import ir, stock


def register():
    Pool.register(
        ir.Cron,
        stock.QuantityIssue,
        stock.QuantityIssueProduct,
        stock.QuantityIssueGenerateStart,
        module='stock_quantity_issue', type_='model')
    Pool.register(
        stock.QuantityIssueGenerate,
        module='stock_quantity_issue', type_='wizard')
    Pool.register(
        stock.QuantityIssueProduction,
        module='stock_quantity_issue', type_='model', depends=['production'])
