'Inventory'
from trytond.osv import fields, OSV, ExceptORM
from trytond.wizard import Wizard, WizardOSV, ExceptWizard
import datetime

STATES = {
    'readonly': "state != 'open'",
}

class Inventory(OSV):
    'Stock Inventory'
    _name = 'stock.inventory'
    _description = __doc__
    _rec_name = 'location'

    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain="[('type', '=', 'storage')]", states=STATES,)
    date = fields.DateTime('Date', readonly=True)
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain="[('type', '=', 'inventory')]", states=STATES,)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Inventory Lines', states=STATES,)
    moves = fields.Many2Many(
        'stock.move', 'inventory_move_rel', 'inventory', 'move',
        'Generated moves')
    state = fields.Selection(
        [('open','Open'),
         ('done','Done'),
         ('cancel','Cancel')],
        'State', readonly=True, select=1)

    def __init__(self):
        super(Inventory, self).__init__()
        self._order.insert(0, ('date', 'DESC'))
        self._rpc_allowed += [
            'set_state_done',
            'set_state_cancel', # TODO remove it and wrap it with a wizard giving a warning.
            ]

    def default_state(self, cursor, user, context=None):
        return 'open'

    def default_date(self, cursor, user, context=None):
        return datetime.datetime.today()

    def set_state_cancel(self, cursor, user, ids, context=None):
        move_obj = self.pool.get("stock.move")
        inventories = self.browse(cursor, user, ids, context=context)
        move_ids = \
            [move.id for inventory in inventories for move in inventory.moves]
        move_obj.set_state_cancel(cursor, user, move_ids, context=context)
        self.write(cursor, user, ids, {'state':'cancel'})

    def set_state_done(self, cursor, user, ids, context=None):
        product_obj = self.pool.get('product.product')
        move_obj = self.pool.get('stock.move')
        inventories = self.browse(cursor, user, ids, context=context)
        location_ids = []
        inv_by_loc = {}

        for inventory in inventories:
            location_ids.append(inventory.location.id)
            inv_by_loc[inventory.location.id] = inventory.id
        raw_data = product_obj.raw_products_by_location(
            cursor, user, location_ids, context=context)

        indexed_data = dict([(line[:3], line[3]) for line in raw_data])

        for inventory in inventories: #!! BUG quand il y a pls uom en stock et que lon encode que une seule !!
            for line in inventory.lines:
                key = (inventory.location.id, line.product.id, line.uom.id)
                expected_qty = indexed_data.get(key, 0.0)
                delta_qty = line.quantity - expected_qty
                indexed_data[key] = 0

                from_location = inventory.lost_found.id
                to_location = inventory.location.id
                if delta_qty < 0:
                    (from_location, to_location, delta_qty) = \
                        (to_location, from_location, -delta_qty)

                move_id = move_obj.create(
                    cursor, user,
                    {'from_location': from_location,
                     'to_location': to_location,
                     'quantity': delta_qty,
                     'product': line.product.id,
                     'uom': line.uom.id,
                     'state': 'done'
                     },
                    context=context,
                    )
        self.write(cursor, user, ids, {'state':'done'})

Inventory()

class InventoryLine(OSV):
    'Stock Inventory Line'
    _name = 'stock.inventory.line'
    _description = __doc__
    _rec_name = 'product'

    product = fields.Many2One(
        'product.product', 'Product', required=True, on_change=['product'],)
    uom = fields.Many2One('product.uom', 'Uom', required=True, select=1,)
    quantity = fields.Float('Quantity', digits=(12, 6),)
    inventory = fields.Many2One('stock.inventory', 'Inventory')

    def __init__(self):
        super(InventoryLine, self).__init__()
        self._sql_constraints += [
            ('check_line_qty_pos',
                'CHECK(quantity >= 0.0)', 'Move quantity must be positive'),
        ]

    def on_change_product(self, cursor, user, ids, value, context=None):
        if 'product' in value and value['product']:
            product = self.pool.get('product.product').browse(
                cursor, user, value['product'])
            return {'uom': product.default_uom.id}
        return {}

InventoryLine()


class CompleteInventory(Wizard):
    'Complete Inventory '
    _name = 'stock.inventory.complete'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_complete',
                'state': 'end',
                },
            },
        }
    def _complete(self, cursor, user, data, context=None):
        line_obj = self.pool.get('stock.inventory.line')
        inventory_obj = self.pool.get('stock.inventory')
        product_obj = self.pool.get('product.product')
        inventories = inventory_obj.browse(cursor, user, data['ids'],
                                           context=context)
        location_ids = []
        inv_by_loc = {}
        for inventory in inventories:
            location_ids.append(inventory.location.id)
            inv_by_loc[inventory.location.id] = inventory.id
            prod_by_loc =  product_obj.products_by_location(
                cursor, user, location_ids, context=context)
        for item in prod_by_loc:
            item['inventory'] = inv_by_loc[item['location']]
            del item['location']
            line_obj.create(cursor, user, item, context=context)

        return {}

CompleteInventory()
