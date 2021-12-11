# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class AbstractShipmentOutCostMixin:
    __slots__ = ()

    @classmethod
    def _column_cost(cls, tables, withs, sign):
        move = tables['move']
        cost = super()._column_cost(tables, withs, sign)
        if Transaction().context.get('include_shipment_cost'):
            cost += Sum(
                sign * cls.cost.sql_cast(move.internal_quantity)
                * Coalesce(move.shipment_out_cost_price, 0))
        return cost


class Context(metaclass=PoolMeta):
    __name__ = 'stock.reporting.margin.context'

    include_shipment_cost = fields.Boolean("Include Shipment Cost")
