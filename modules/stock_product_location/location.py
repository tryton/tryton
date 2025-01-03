# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval, If


class ProductLocation(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    "It defines the default storage location by warehouse for a product"
    __name__ = 'stock.product.location'
    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ])
    product = fields.Many2One(
        'product.product', "Variant", ondelete='CASCADE',
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ])
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[('type', '=', 'warehouse')], ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Storage Location',
        required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', If(Bool(Eval('warehouse')),
                    [Eval('warehouse')], [])),
            ])

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def set_product_location(self, field='to_location', **pattern):
        "Set the product location on the field"
        assert field in {'from_location', 'to_location'}
        location = self.get_product_location(**pattern)
        if location:
            setattr(self, field, location)

    def get_product_location(self, **pattern):
        "Return the product location for the move"
        if (getattr(self, 'shipment', None)
                and getattr(self.shipment, 'warehouse', None)):
            pattern.setdefault('warehouse', self.shipment.warehouse.id)
        elif getattr(self, 'production', None):
            pattern.setdefault('warehouse', self.production.warehouse.id)

        if self.product:
            pattern.setdefault('template', self.product.template.id)
            pattern.setdefault('product', self.product.id)

        locations = self.product.locations + self.product.template.locations
        for product_location in locations:
            if product_location.match(pattern):
                return product_location.location

    @property
    def _default_pick_location(self):
        location = super()._default_pick_location
        if self.product.consumable:
            if ((product_location := self.get_product_location())
                    and product_location.type != 'view'):
                location = product_location
        return location


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move:
            move.set_product_location(warehouse=self.warehouse.id)
        return move


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move:
            move.set_product_location(warehouse=self.warehouse.id)
        return move
