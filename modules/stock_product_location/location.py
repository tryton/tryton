# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (ModelView, ModelSQL, MatchMixin, fields,
    sequence_ordered)
from trytond.pyson import If, Eval, Bool
from trytond import backend
from trytond.pool import PoolMeta

__all__ = ['ProductLocation', 'Move', 'ShipmentIn', 'ShipmentOutReturn']


class ProductLocation(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    '''
    Product Location
    It defines the default storage location by warehouse for a product.
    '''
    __name__ = 'stock.product.location'
    product = fields.Many2One('product.product', 'Product', required=True,
        select=True, ondelete='CASCADE')
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
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(ProductLocation, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'

    def set_product_location(self, field='to_location', **pattern):
        assert field in {'from_location', 'to_location'}
        if getattr(self, 'shipment', None):
            pattern.setdefault('warehouse', self.shipment.warehouse.id)

        for product_location in self.product.locations:
            if product_location.match(pattern):
                setattr(self, field, product_location.location)
                break


class ShipmentIn:
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.in'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentIn, cls)._get_inventory_moves(incoming_move)
        if move:
            move.set_product_location(
                warehouse=incoming_move.shipment.warehouse.id)
        return move


class ShipmentOutReturn:
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentOutReturn, cls)._get_inventory_moves(
            incoming_move)
        if move:
            move.set_product_location(
                warehouse=incoming_move.shipment.warehouse.id)
        return move
