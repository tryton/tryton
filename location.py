#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import If, Eval, Bool


class ProductLocation(ModelSQL, ModelView):
    '''
    Product Location defines the default storage location
    by warehouse for a product
    '''
    _name = 'stock.product.location'
    _description = 'Product Location'

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
    sequence = fields.Integer('Sequence', required=True)

    def __init__(self):
        super(ProductLocation, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

ProductLocation()


class ShipmentIn(ModelSQL, ModelView):
    _name = 'stock.shipment.in'

    def _get_inventory_moves(self, incoming_move):
        res = super(ShipmentIn, self)._get_inventory_moves(incoming_move)
        for product_location in incoming_move.product.locations:
            if product_location.warehouse.id != \
                    incoming_move.shipment_in.warehouse.id:
                continue
            res['to_location'] = product_location.location.id
        return res

ShipmentIn()
