# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (ModelView, ModelSQL, MatchMixin, fields,
    sequence_ordered)
from trytond.pyson import If, Eval, Bool
from trytond.pool import PoolMeta


class ProductLocation(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    '''
    Product Location
    It defines the default storage location by warehouse for a product.
    '''
    __name__ = 'stock.product.location'
    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ],
        depends=['product'])
    product = fields.Many2One(
        'product.product', "Variant", ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        depends=['template'])
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[('type', '=', 'warehouse')], ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Storage Location',
        required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', If(Bool(Eval('warehouse')),
                    [Eval('warehouse')], [])),
            ], depends=['warehouse'])

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        super().__register__(module_name)

        # Migration from 5.6: Add template on locations
        table.not_null_action('product', 'remove')

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def set_product_location(self, field='to_location', **pattern):
        assert field in {'from_location', 'to_location'}
        if getattr(self, 'shipment', None):
            pattern.setdefault('warehouse', self.shipment.warehouse.id)

        if self.product:
            pattern.setdefault('template', self.product.template.id)
            pattern.setdefault('product', self.product.id)

        locations = self.product.locations + self.product.template.locations
        for product_location in locations:
            if product_location.match(pattern):
                setattr(self, field, product_location.location)
                break


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
