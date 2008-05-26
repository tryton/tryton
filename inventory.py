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
        domain="[('type', '=', 'lost_found')]", states=STATES,)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Inventory Lines', states=STATES,)
    moves = fields.Many2Many(
        'stock.move', 'inventory_move_rel', 'inventory', 'move',
        'Generated moves')
    company = fields.Many2One(
        'company.company', 'Company', required=True, states=STATES,)


    state = fields.Selection(
        [('open','Open'),
         ('done','Done'),
         ('cancel','Cancel')],
        'State', readonly=True, select=1)

    def __init__(self):
        super(Inventory, self).__init__()
        self._order.insert(0, ('date', 'DESC'))
        self._rpc_allowed += [
                'set_state_cancel',
                'set_state_open',
                'set_state_done',
        ]

    def default_state(self, cursor, user, context=None):
        return 'open'

    def default_date(self, cursor, user, context=None):
        return datetime.datetime.today()

    def default_company(self, cursor, user, context=None):
        if context.get('company'):
            return context.get('company')
        user_obj = self.pool.get('res.user')
        user = user_obj.browse(cursor, user, user, context=context)
        return user.company.id

    def set_state_cancel(self, cursor, user, ids, context=None):
        self.write(cursor, user, ids, {
            'state': 'cancel',
            }, context=context)

    def set_state_open(self, cursor, user, ids, context=None):
        self.write(cursor, user, ids, {
            'state': 'open',
            }, context=context)

    def set_state_done(self, cursor, user, ids, context=None):
        self.write(cursor, user, ids, {
            'state': 'done',
            }, context=context)

    def _cancel(self, cursor, user, ids, context=None):
        move_obj = self.pool.get("stock.move")
        inventories = self.browse(cursor, user, ids, context=context)
        move_ids = \
            [move.id for inventory in inventories for move in inventory.moves]
        return move_obj.set_state_cancel(cursor, user, move_ids, context=context)

    def _done(self, cursor, user, ids, context=None):
        product_obj = self.pool.get('product.product')
        move_obj = self.pool.get('stock.move')
        inventories = self.browse(cursor, user, ids, context=context)
        location_ids = []
        inv_by_loc = {}

        for inventory in inventories:
            location_ids.append(inventory.location.id)
            inv_by_loc[inventory.location.id] = inventory.id
        raw_data = product_obj.raw_products_by_location(cursor, user,
                location_ids, context=context)

        indexed_data = {}
        for location, product, uom, qty in raw_data:
            indexed_data.setdefault(location,{})[(product, uom)] = qty

        for inventory in inventories:
            if inventory.state != 'open':
                continue
            moves = []
            location_data = indexed_data.get(inventory.location.id, {})
            for line in inventory.lines:
                key = (line.product.id, line.uom.id)
                expected_qty = location_data.get(key, 0.0)
                delta_qty = line.quantity - expected_qty
                location_data[key] = 0

                from_location = inventory.lost_found.id
                to_location = inventory.location.id
                if delta_qty < 0:
                    (from_location, to_location, delta_qty) = \
                        (to_location, from_location, -delta_qty)

                move_id = move_obj.create(cursor, user, {
                    'from_location': from_location,
                    'to_location': to_location,
                    'quantity': delta_qty,
                    'product': line.product.id,
                    'uom': line.uom.id,
                    'company': inventory.company.id,
                    'state': 'done',
                    }, context=context)
                moves.append(move_id)
            # Create move for all missing products
            for (product, uom), qty in location_data.iteritems():
                if qty == 0:
                    continue
                from_location = inventory.location.id
                to_location = inventory.lost_found.id
                if qty < 0:
                    (from_location, to_location, qty) = \
                        (to_location, from_location, -qty)

                move_id = move_obj.create(cursor, user, {
                    'from_location': from_location,
                    'to_location': to_location,
                    'quantity': qty,
                    'product': product,
                    'uom': uom,
                    'company': inventory.company.id,
                    'state': 'done',
                    }, context=context)
                moves.append(move_id)

        return self.write(cursor, user, ids, {
            'date': datetime.datetime.today(),
            'moves': [('add', x) for x in moves],
            }, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'state' in vals:
            if vals['state'] == 'done':
                self._done(cursor, user, ids, context=context)
            elif vals['state'] == 'cancel':
                self._cancel(cursor, user, ids, context=context)
        return super(Inventory, self).write(cursor, user, ids, vals,
                context=context)

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
            ('inventory_product_uniq', 'UNIQUE(inventory, product)',
                'Product must be unique by inventory!'),
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

        pbl =  product_obj.products_by_location(
            cursor, user, location_ids, context=context)
        indexed_data = {}
        for line in pbl:
            indexed_data.setdefault(line['location'], []).append(
                (line['product'], line['uom'], line['quantity']))

        for inventory in inventories:
            products = [line.product.id for line in inventory.lines]
            for (product, uom, qty) in indexed_data.get(inventory.location.id,[]):
                # Skip products already in the inventory:
                if product in products:
                    continue
                if qty <= 0.0:
                    qty = 0
                line_obj.create(
                    cursor, user,
                    {'product': product,
                     'uom': uom,
                     'quantity': qty,
                     'inventory': inventory.id,},
                    context=context)
        return {}

CompleteInventory()
