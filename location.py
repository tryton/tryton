#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import If, Eval, Bool
from trytond.transaction import Transaction
from trytond.backend import TableHandler
from trytond.pool import PoolMeta

__all__ = ['ProductLocation', 'ShipmentIn', 'ShipmentOutReturn']
__metaclass__ = PoolMeta


class ProductLocation(ModelSQL, ModelView):
    '''
    Product Location
    It defines the default storage location by warehouse for a product.
    '''
    __name__ = 'stock.product.location'
    product = fields.Many2One('product.product', 'Product', required=True,
            select=True)
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
            domain=[('type', '=', 'warehouse')])
    location = fields.Many2One('stock.location', 'Storage Location',
        required=True, domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', If(Bool(Eval('warehouse')),
                    [Eval('warehouse')], [])),
            ], depends=['warehouse'])
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')

    @classmethod
    def __setup__(cls):
        super(ProductLocation, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(ProductLocation, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')


class ShipmentIn:
    __name__ = 'stock.shipment.in'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentIn, cls)._get_inventory_moves(incoming_move)
        for product_location in incoming_move.product.locations:
            if product_location.warehouse.id != \
                    incoming_move.shipment.warehouse.id:
                continue
            move.to_location = product_location.location
        return move


class ShipmentOutReturn:
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentOutReturn, cls)._get_inventory_moves(
            incoming_move)
        for product_location in incoming_move.product.locations:
            if (product_location.warehouse
                    == incoming_move.shipment.warehouse):
                move.to_location = product_location.location
        return move
