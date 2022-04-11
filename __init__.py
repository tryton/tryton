# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.stock.stock_reporting_margin import Abstract
from trytond.pool import Pool

from . import carrier, stock, stock_reporting_margin

__all__ = ['register']


def register():
    Pool.register(
        carrier.Carrier,
        stock.Move,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock_reporting_margin.Context,
        module='stock_shipment_cost', type_='model')
    Pool.register(
        module='stock_shipment_cost', type_='wizard')
    Pool.register(
        module='stock_shipment_cost', type_='report')
    Pool.register_mixin(
        stock_reporting_margin.AbstractShipmentOutCostMixin, Abstract,
        module='stock_shipment_cost')
