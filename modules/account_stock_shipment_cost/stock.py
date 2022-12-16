# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    shipment_costs = fields.Many2Many(
        'account.shipment_cost-stock.shipment.out',
        'shipment', 'shipment_cost', "Shipment Costs", readonly=True)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    shipment_costs = fields.Many2Many(
        'account.shipment_cost-stock.shipment.out.return',
        'shipment', 'shipment_cost', "Shipment Costs", readonly=True)
