# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.stock.exceptions import MoveValidationError


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    cost_warehouse = fields.Many2One(
        'stock.location', "Cost Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'invisible': (
                (Eval('type') != 'storage')
                | Bool(Eval('warehouse'))
                | (Eval('id', -1) < 0)),
            },
        depends=['type', 'warehouse'])


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @property
    def from_cost_warehouse(self):
        return (self.from_location.warehouse
            or self.from_location.cost_warehouse)

    @property
    def to_cost_warehouse(self):
        return (self.to_location.warehouse
            or self.to_location.cost_warehouse)

    @property
    def cost_warehouse(self):
        return self.from_cost_warehouse or self.to_cost_warehouse

    @classmethod
    def validate(cls, moves):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        super().validate(moves)
        config = Configuration(1)
        transit_locations = {}
        for move in moves:
            company = move.company
            if company not in transit_locations:
                transit_location = config.get_multivalue(
                    'shipment_internal_transit', company=company)
                transit_locations[company] = transit_location
            else:
                transit_location = transit_locations[company]
            if (company.cost_price_warehouse
                    and move.from_location.type == 'storage'
                    and move.from_location != transit_location
                    and move.to_location.type == 'storage'
                    and move.to_location != transit_location):
                if move.from_cost_warehouse != move.to_cost_warehouse:
                    raise MoveValidationError(gettext(
                            'product_cost_warehouse'
                            '.msg_move_storage_location_same_warehouse',
                            from_=move.from_location.rec_name,
                            to=move.to_location.rec_name))

    @property
    def _cost_price_pattern(self):
        pattern = super()._cost_price_pattern
        if self.company.cost_price_warehouse:
            pattern['warehouse'] = (
                self.cost_warehouse.id if self.cost_warehouse else None)
        return pattern

    def _cost_price_key(self):
        key = super()._cost_price_key()
        if self.company.cost_price_warehouse:
            key += (('warehouse',
                    (self.cost_warehouse.id if self.cost_warehouse else None)),
                )
        return key

    @classmethod
    def _cost_price_context(cls, moves):
        pool = Pool()
        Location = pool.get('stock.location')
        context = super()._cost_price_context(moves)
        if moves[0].company.cost_price_warehouse:
            warehouse = moves[0].cost_warehouse
            locations = Location.search([
                    ('type', '=', 'storage'),
                    ['OR',
                        ('parent', 'child_of',
                            warehouse.id if warehouse else []),
                        ('cost_warehouse', '=',
                            warehouse.id if warehouse else None),
                        ],
                    ])
            context['locations'] = [l.id for l in locations]
        return context

    def get_fifo_move(self, quantity=0.0, date=None):
        warehouse = self.cost_warehouse.id if self.cost_warehouse else None
        with Transaction().set_context(warehouse=warehouse):
            return super().get_fifo_move(quantity=quantity, date=date)


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @fields.depends('company')
    def on_change_with_transit_location(self, name=None):
        pool = Pool()
        Config = pool.get('stock.configuration')
        location = super().on_change_with_transit_location(name=name)
        if not location and self.company and self.company.cost_price_warehouse:
            location = Config(1).get_multivalue('shipment_internal_transit').id
        return location
