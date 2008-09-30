#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.osv import fields, OSV


class ProductLocation(OSV):
    '''
    Product Location defines the default storage location
        by warehouse for a product
    '''
    _name = 'stock.product.location'
    _description = 'Product Location'

    product = fields.Many2One('product.product', 'Product', required=True,
            select=1)
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
            domain=[('type', '=', 'warehouse')])
    location = fields.Many2One('stock.location', 'Storage Location',
            required=True, domain="[('type', '=', 'storage'), " \
                "('parent', 'child_of', [warehouse])]")
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(ProductLocation, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

ProductLocation()


class PackingIn(OSV):
    _name = 'stock.packing.in'

    def _get_inventory_moves(self, cursor, user, incoming_move, context=None):
        res = super(PackingIn, self)._get_inventory_moves(cursor, user,
                incoming_move, context=context)
        for product_location in incoming_move.product.locations:
            if product_location.warehouse.id != \
                    incoming_move.packing_in.warehouse.id:
                continue
            res['to_location'] = product_location.location.id
        return res

PackingIn()
