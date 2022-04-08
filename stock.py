# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.product import round_price
from trytond.modules.stock.exceptions import MoveValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipment_internal_transit.domain = [
            cls.shipment_internal_transit.domain,
            ('cost_warehouse', '=', None),
            ]


class ConfigurationLocation(metaclass=PoolMeta):
    __name__ = 'stock.configuration.location'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipment_internal_transit.domain = [
            cls.shipment_internal_transit.domain,
            ('cost_warehouse', '=', None),
            ]


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
            })


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @property
    def from_warehouse(self):
        return super().from_warehouse or self.from_location.cost_warehouse

    @property
    def to_warehouse(self):
        return super().to_warehouse or self.to_location.cost_warehouse

    @fields.depends('company', 'from_location', 'to_location')
    def on_change_with_cost_price_required(self, name=None):
        required = super().on_change_with_cost_price_required(name=name)
        if (self.company and self.company.cost_price_warehouse
                and self.from_location and self.to_location
                and self.from_warehouse != self.to_warehouse):
            required = True
        return required

    @classmethod
    def get_unit_price_company(cls, moves, name):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        Uom = pool.get('product.uom')
        prices = super().get_unit_price_company(moves, name)
        for move in moves:
            if (move.company.cost_price_warehouse
                    and move.from_warehouse != move.to_warehouse
                    and move.to_warehouse
                    and isinstance(move.shipment, ShipmentInternal)):
                cost = total_qty = 0
                for outgoing_move in move.shipment.outgoing_moves:
                    if outgoing_move.product == move.product:
                        qty = Uom.compute_qty(
                            outgoing_move.uom, outgoing_move.quantity,
                            move.product.default_uom)
                        qty = Decimal(str(qty))
                        cost += qty * outgoing_move.cost_price
                        total_qty += qty
                if cost and total_qty:
                    cost_price = round_price(cost / total_qty)
                    prices[move.id] = cost_price
        return prices

    def get_cost_price(self, product_cost_price=None):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        cost_price = super().get_cost_price(
            product_cost_price=product_cost_price)
        if (self.company.cost_price_warehouse
                and self.from_warehouse != self.to_warehouse
                and self.to_warehouse
                and isinstance(self.shipment, ShipmentInternal)):
            cost_price = self.unit_price_company
        return cost_price

    @classmethod
    def validate(cls, moves):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        super().validate(moves)
        config = Configuration(1)
        transit_locations = {}
        for move in moves:
            if move.state in {'staging', 'draft'}:
                continue
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
                if move.from_warehouse != move.to_warehouse:
                    raise MoveValidationError(gettext(
                            'product_cost_warehouse'
                            '.msg_move_storage_location_same_warehouse',
                            from_=move.from_location.rec_name,
                            to=move.to_location.rec_name))

    def _do(self):
        cost_price, to_save = super()._do()
        if (self.company.cost_price_warehouse
                and self.from_location.type == 'storage'
                and self.to_location.type == 'storage'
                and self.from_warehouse != self.to_warehouse):
            if self.from_warehouse:
                cost_price = self._compute_product_cost_price('out')
            elif self.to_warehouse:
                cost_price = self._compute_product_cost_price(
                    'in', self.unit_price_company)
        return cost_price, to_save

    @property
    def _cost_price_pattern(self):
        pattern = super()._cost_price_pattern
        if self.company.cost_price_warehouse:
            pattern['warehouse'] = (
                self.warehouse.id if self.warehouse else None)
        return pattern

    def _cost_price_key(self):
        key = super()._cost_price_key()
        if self.company.cost_price_warehouse:
            key += (('warehouse',
                    (self.warehouse.id if self.warehouse else None)),
                )
        return key

    @classmethod
    def _cost_price_context(cls, moves):
        pool = Pool()
        Location = pool.get('stock.location')
        context = super()._cost_price_context(moves)
        if moves[0].company.cost_price_warehouse:
            warehouse = moves[0].warehouse
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
        warehouse = self.warehouse.id if self.warehouse else None
        with Transaction().set_context(warehouse=warehouse):
            return super().get_fifo_move(quantity=quantity, date=date)

    def _get_account_stock_move_type(self):
        type_ = super()._get_account_stock_move_type()
        if (self.company.cost_price_warehouse
                and self.from_location.type == 'storage'
                and self.to_location.type == 'storage'
                and self.from_warehouse != self.to_warehouse):
            if self.from_warehouse and not self.to_warehouse:
                type_ = 'out_warehouse'
            elif not self.from_warehouse and self.to_warehouse:
                type_ = 'in_warehouse'
        return type_


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @fields.depends('company')
    def on_change_with_transit_location(self, name=None):
        pool = Pool()
        Config = pool.get('stock.configuration')
        location = super().on_change_with_transit_location(name=name)
        if not location and self.company and self.company.cost_price_warehouse:
            location = Config(1).get_multivalue(
                'shipment_internal_transit', company=self.company)
            if location:
                location = location.id
        return location
