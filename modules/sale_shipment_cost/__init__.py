# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, party, sale, stock
from .stock import ShipmentCostSaleMixin

__all__ = ['register', 'ShipmentCostSaleMixin']


def register():
    Pool.register(
        party.Party,
        party.PartySaleMethod,
        account.InvoiceLine,
        sale.Configuration,
        sale.ConfigurationSaleMethod,
        sale.Sale,
        sale.Line,
        stock.ShipmentCostSale,
        stock.ShipmentOut,
        module='sale_shipment_cost', type_='model')
    Pool.register(
        sale.Promotion,
        module='sale_shipment_cost', type_='model',
        depends=['sale_promotion'])
    Pool.register(
        sale.ReturnSale,
        module='sale_shipment_cost', type_='wizard')
