#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
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
        domain="[('type', '=', 'storage')]", states=STATES)
    date = fields.Date('Date')
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain="[('type', '=', 'lost_found')]", states=STATES)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Inventory Lines', states=STATES)
    moves = fields.Many2Many(
        'stock.move', 'inventory_move_rel', 'inventory', 'move',
        'Generated moves')
    company = fields.Many2One(
        'company.company', 'Company', required=True, states=STATES)


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
        return datetime.date.today()

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
            if inventory.state != 'open':
                continue
            moves = []
            for line in inventory.lines:
                delta_qty = line.expected_quantity - line.quantity
                if delta_qty == 0.0:
                    continue
                from_location = inventory.location.id
                to_location = inventory.lost_found.id
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

            self.write(cursor, user, ids, {
                    'date': datetime.date.today(),
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

    product = fields.Many2One('product.product', 'Product', required=True,
            on_change=['product'])
    uom = fields.Many2One('product.uom', 'UOM', required=True, select=1,
            readonly=True)
    expected_quantity = fields.Float('Expected Quantity', digits=(12, 6),
            readonly=True)
    quantity = fields.Float('Quantity', digits=(12, 6))
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
        uom_obj = self.pool.get('product.uom')
        inventories = inventory_obj.browse(cursor, user, data['ids'],
                context=context)

        for inventory in inventories:
            # Compute product quantities
            if inventory.date:
                context = context.copy()
                context['stock_date'] = inventory.date
                pbl = product_obj.products_by_location(
                    cursor, user, [inventory.location.id],
                    context=context)
            else:
                pbl = product_obj.products_by_location(
                    cursor, user, [inventory.location.id], context=context)
            # Index some data
            uom_by_id = {}
            for uom in uom_obj.browse(
                cursor, user, [line['uom'] for line in pbl], context=context):
                uom_by_id[uom.id] = uom
            product_qty = {}
            for line in pbl:
                product_qty[line['product']] = (line['quantity'],
                                                uom_by_id[line['uom']])
            # Update existing lines
            for line in inventory.lines:
                if line.product.id in product_qty:
                    quantity, uom = product_qty[line.product.id]
                    del product_qty[line.product.id]
                    # if nothing as changed, continue
                    if line.quantity == line.expected_quantity == quantity \
                            and line.uom.id == uom.id:
                        continue
                    values = {'expected_quantity': quantity,
                              'uom': uom.id}
                    # update also quantity field if not edited
                    if line.quantity == line.expected_quantity:
                        values['quantity'] = quantity
                else:
                    values = {'expected_quantity': 0.0,}
                    if line.quantity == line.expected_quantity:
                        values['quantity'] = 0


                line_obj.write(
                    cursor, user, line.id, values, context=context)

            # Create lines if needed
            for product in product_qty:
                quantity, uom = product_qty[product]
                values = {
                    'product': product,
                    'expected_quantity': quantity,
                    'quantity': quantity,
                    'uom': uom.id,
                    'inventory': inventory.id,
                    }
                line_obj.create(
                    cursor, user, values, context=context)

        return {}

CompleteInventory()
