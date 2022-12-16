# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class AbstractCommissionMixin:
    __slots__ = ()

    @classmethod
    def _column_cost(cls, tables, withs, sign):
        pool = Pool()
        Move = pool.get('stock.move')
        move = tables['move']
        cost = super()._column_cost(tables, withs, sign)
        if (Transaction().context.get('include_commission')
                and 'commission_price' in Move._fields):
            cost -= Sum(
                sign * cls.cost.sql_cast(move.internal_quantity)
                * Coalesce(move.commission_price, 0))
        return cost


class Context(metaclass=PoolMeta):
    __name__ = 'stock.reporting.margin.context'

    include_commission = fields.Boolean("Include Commission")

    @classmethod
    def default_include_commission(cls):
        return Transaction().context.get('include_commission', False)
