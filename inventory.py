'Inventory'
from trytond.osv import fields, OSV, ExceptORM
import time


class InventoryDay(OSV):
    'Stock Inventory Day'
    _name = 'stock.inventory.day'
    _description = __doc__
    _rec_name = 'date'
    _order = 'date'

    date = fields.Date('Date', readonly=True)
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain='[('type', '=', 'inventory')]',)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True, states=STATES,
        domain="[('type', '=', 'warehouse')]",)
    inventories = fields.One2Many(
        'stock.inventory', 'inventory_day', 'Inventories')
    state = fields.Selection(
        [('draft','Draft'),('done','Done')], 'State', readonly=True,)

    # TODO name_get : date - wh
    # TODO constrain: one open date by location

    def set_state_draft(self, cursor, user, ids, context=None):
        #TODO
        self.write(cursor, user, ids, {'state','draft'})

    def _location_amount(self, cursor, user, target_uom,
                             qty_uom, uom_index, context=None):
        """
        Take a raw list of quantities and uom and convert it to
        the target uom.
        """
        uom_obj = self.pool.get('product.uom')
        res = 0
        for uom,qty in qty_uom:
            res += uom_obj.compute_qty(
                cursor, user, uom_index[uom], qty, uom_index[target_uom])
        return res

    # FIXME : factorize code above, to mush level of loop under.

    def set_state_done(self, cursor, user, ids, context=None):
        product_obj = self.pool.get('product.product')
        move_obj = self.pool.get('product.uom')

        for inventory_day in self.browse(cursor, user, ids, context=context):
            location_ids = []
            inv_by_loc = {}

            for inventory in inventories:
                location_ids.append(inventory.location.id)
                inv_by_loc[inventory.location.id] = inventory.id
            raw_data = product_obj.raw_product_by_location(
                cursor, user, location_ids, context=context):

            processed_data = {}
            for line in raw_data:
                if line[:2] in processed_data:
                    processed_data[line[:2]].append(line[2:])
                else:
                    processed_data[line[:2]] = [line[2:]]

            for inventory in inventories:
                moves = []
                for line in inventory.lines:
                    qty = self._location_amount(
                        cursor, user, line.uom.id,
                        processed_data[(inventory.location.id, line.product.id)],
                        uom_index, context=context,)
                    qty = line.quantity - qty
                    from_location = inventory.date.lost_found.id
                    to_location = inventory.location.id
                    if qty<0:
                        (from_location, to_location, qty) = \
                            (to_location, from_location, -qty)
                    move_id = move_obj.create(
                        cursor, user,
                        {
                            'from_location': from_location,
                            'to_location': to_location,
                            'quantity': qty,
                            'product': line.product.id,
                            'uom': line.uom.id,
                         },
                        context=context,
                        )
                    moves.append(move_id)
                inventory_obj.write(
                    cursor, user, inventory.id,
                    {'moves': [('add',moves)], 'state': 'done'})

        self.write(cursor, user, ids, {'state','done'})

InventoryDay()

class Inventory(OSV):
    'Stock Inventory'
    _name = 'stock.inventory'
    _description = __doc__
    _rec_name = 'location'

    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain='[('type', '=', 'store')]',)
    inventory_day = fields.Many2One('stock.inventory.day', "Inventory Day", required=True)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Inventory Lines', readonly=True,)
    moves = fields.Many2Many('stock.move', 'inventory', 'move', 'Moves')
    state = fields.Selection(
        [('draft','Draft'),('done','Done')], 'State', readonly=True,)

    def __init__(self):
        super(Move, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_draft',
            ]

    def default_state(self, cursor, user, context=None):
        return 'draft'

    #TODO :
    # - constraint on location : unique by day.
    # -             "          : child of day warehouse.

Inventory()

class InventoryLine(OSV):
    'Stock Inventory Line'
    _name = 'stock.inventory.line'
    _description = __doc__
    _rec_name = 'product'

    product = fields.Many2One(
        'product.product', 'Product', required=True,)
    uom = fields.Many2One('product.uom', 'Uom', required=True, select=1,)
    quantity = fields.Float('Quantity', digits=(12, 6),)
    inventory = fields.Many2One('stock.inventory', 'Inventory')

    # TODO constrain : unique (product,uom,inventory)

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
        product_obj = self.pool.get('product.product')
        inventories = inventory_obj.browse(cursor, user, data['ids'],
                                           context=context)
        locations_ids = []
        inv_by_loc = {}
        for inventory in inventories:
            location_ids.append(inventory.location.id)
            inv_by_loc[inventory.location.id] = inventory.id
        prod_by_loc =  product_obj.product_by_location(
            cursor, user, location_ids, context=context):

        for item in prod_by_loc:
            item['inventory'] = inv_by_loc[item['location']]
            del item['location']
            line_obj.create(cursor, user, item, context=context)


CompleteInventory()
