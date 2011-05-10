#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
'Inventory'
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.wizard import Wizard

STATES = {
    'readonly': "state != 'draft'",
}


class Inventory(ModelWorkflow, ModelSQL, ModelView):
    'Stock Inventory'
    _name = 'stock.inventory'
    _description = __doc__
    _rec_name = 'location'

    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': "state != 'draft' or bool(lines)",
        })
    date = fields.Date('Date', required=True, states={
            'readonly': "state != 'draft' or bool(lines)",
        })
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')], states=STATES)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Lines', states=STATES)
    company = fields.Many2One(
        'company.company', 'Company', required=True, states={
            'readonly': "state != 'draft' or bool(lines)",
        })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True, select=1)

    def __init__(self):
        super(Inventory, self).__init__()
        self._order.insert(0, ('date', 'DESC'))

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def default_lost_found(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.lost_found.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def set_state_draft(self, cursor, user, inventory_id, context=None):
        self.write(cursor, user, inventory_id, {
            'state': 'draft',
            }, context=context)

    def set_state_cancel(self, cursor, user, inventory_id, context=None):
        line_obj = self.pool.get("stock.inventory.line")
        inventory = self.browse(cursor, user, inventory_id, context=context)
        line_obj.cancel_move(cursor, user, inventory.lines, context=context)
        self.write(cursor, user, inventory_id, {
            'state': 'cancel',
            }, context=context)

    def set_state_done(self, cursor, user, inventory_id, context=None):
        date_obj = self.pool.get('ir.date')
        line_obj = self.pool.get('stock.inventory.line')
        inventory = self.browse(cursor, user, inventory_id, context=context)

        for line in inventory.lines:
            line_obj.create_move(cursor, user, line, context=context)
        self.write(cursor, user, inventory_id, {
            'state': 'done',
            }, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        date_obj = self.pool.get('ir.date')
        line_obj = self.pool.get('stock.inventory.line')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['date'] = date_obj.today(cursor, user, context=context)
        default['lines'] = False

        new_ids = []
        for inventory in self.browse(cursor, user, ids, context=context):
            new_id = super(Inventory, self).copy(cursor, user, inventory.id,
                    default=default, context=context)
            line_obj.copy(cursor, user, [x.id for x in inventory.lines],
                    default={
                        'inventory': new_id,
                        'move': False,
                        }, context=context)
            self.complete_lines(cursor, user, new_id, context=context)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def complete_lines(self, cursor, user, ids, context=None):
        '''
        Complete or update the inventories

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the ids of stock.inventory
        :param context: the context
        '''
        line_obj = self.pool.get('stock.inventory.line')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]

        inventories = self.browse(cursor, user, ids,
                context=context)
        context = context and context.copy() or {}

        for inventory in inventories:
            # Compute product quantities
            ctx = context and context.copy() or {}
            ctx['stock_date_end'] = inventory.date
            pbl = product_obj.products_by_location(
                cursor, user, [inventory.location.id], context=ctx)

            # Index some data
            product2uom = {}
            product2type = {}
            for product in product_obj.browse(cursor, user,
                    [line[1] for line in pbl], context=context):
                product2uom[product.id] = product.default_uom.id
                product2type[product.id] = product.type

            product_qty = {}
            for (location, product), quantity in pbl.iteritems():
                product_qty[product] = (quantity, product2uom[product])

            # Update existing lines
            for line in inventory.lines:
                if not (line.product.active and
                        line.product.type == 'stockable'):
                    line_obj.delete(cursor, user, line.id, context=context)
                    continue
                if line.product.id in product_qty:
                    quantity, uom_id = product_qty.pop(line.product.id)
                elif line.product.id in product2uom:
                    quantity, uom_id = 0.0, product2uom[line.product.id]
                else:
                    quantity, uom_id = 0.0, line.product.default_uom.id
                values = line_obj.update_values4complete(cursor, user,
                        line, quantity, uom_id, context=context)
                if values:
                    line_obj.write(cursor, user, line.id, values,
                            context=context)

            # Create lines if needed
            for product_id in product_qty:
                if product2type[product_id] != 'stockable':
                    continue
                quantity, uom_id = product_qty[product_id]
                values = line_obj.create_values4complete(cursor, user,
                        product_id, inventory, quantity, uom_id,
                        context=context)
                line_obj.create(cursor, user, values, context=context)

Inventory()


class InventoryLine(ModelSQL, ModelView):
    'Stock Inventory Line'
    _name = 'stock.inventory.line'
    _description = __doc__
    _rec_name = 'product'

    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('type', '=', 'stockable')], on_change=['product'])
    uom = fields.Function('get_uom', type='many2one', relation='product.uom',
            string='UOM')
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits')
    expected_quantity = fields.Float('Expected Quantity',
            digits="(16, unit_digits)", readonly=True)
    quantity = fields.Float('Quantity', digits="(16, unit_digits)")
    move = fields.Many2One('stock.move', 'Move', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Inventory', required=True,
            ondelete='CASCADE')

    def __init__(self):
        super(InventoryLine, self).__init__()
        self._sql_constraints += [
            ('check_line_qty_pos',
                'CHECK(quantity >= 0.0)', 'Line quantity must be positive!'),
            ('inventory_product_uniq', 'UNIQUE(inventory, product)',
                'Product must be unique by inventory!'),
        ]
        self._order.insert(0, ('product', 'ASC'))

    def default_unit_digits(self, cursor, user, context=None):
        return 2

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        res = {}
        res['unit_digits'] = 2
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            res['uom'] = product.default_uom.id
            res['uom.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def get_uom(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.product.default_uom.id
        return res

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            res[line.id] = line.product.default_uom.digits
        return res

    def cancel_move(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('stock.move')
        move_obj.write(
            cursor, user, [l.move.id for l in lines if l.move], {'state': 'cancel'},
            context=context)
        move_obj.delete(
            cursor, user, [l.move.id for l in lines if l.move], context=context)
        self.write(
            cursor, user, [l.id for l in lines if l.move], {'move': False},
            context=context)

    def create_move(self, cursor, user, line, context=None):
        '''
        Create move for an inventory line

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of inventory.line
        :param context: the context
        :return: the stock.move id or None
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')

        delta_qty = uom_obj.compute_qty(line.uom,
            line.expected_quantity - line.quantity,
            line.uom)
        if delta_qty == 0.0:
            return
        from_location = line.inventory.location.id
        to_location = line.inventory.lost_found.id
        if delta_qty < 0:
            (from_location, to_location, delta_qty) = \
                (to_location, from_location, -delta_qty)

        move_id = move_obj.create(cursor, user, {
            'from_location': from_location,
            'to_location': to_location,
            'quantity': delta_qty,
            'product': line.product.id,
            'uom': line.uom.id,
            'company': line.inventory.company.id,
            'state': 'done',
            'effective_date': line.inventory.date,
            }, context=context)
        self.write(cursor, user, line.id, {'move': move_id}, context=context)
        return move_id

    def update_values4complete(self, cursor, user, line, quantity, uom_id,
            context=None):
        '''
        Return update values to complete inventory

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of inventory.line
        :param quantity: the actual product quantity for the inventory location
        :param uom_id: the UoM id of the product line
        :param context: the context
        :return: a dictionary
        '''
        res = {}
        # if nothing changed, no update
        if line.quantity == line.expected_quantity == quantity \
                and line.uom.id == uom_id:
            return {}
        res['expected_quantity'] = quantity
        res['uom'] = uom_id
        # update also quantity field if not edited
        if line.quantity == line.expected_quantity:
            res['quantity'] = max(quantity, 0.0)
        return res

    def create_values4complete(self, cursor, user, product_id, inventory,
            quantity, uom_id, context=None):
        '''
        Return create values to complete inventory

        :param cursor: the database cursor
        :param user: the user id
        :param product_id: the product.product id
        :param inventory: a BrowseRecord of inventory.inventory
        :param quantity: the actual product quantity for the inventory location
        :param uom_id: the UoM id of the product_id
        :param context: the context
        :return: a dictionary
        '''
        return {
            'inventory': inventory.id,
            'product': product_id,
            'expected_quantity': quantity,
            'quantity': max(quantity, 0.0),
            'uom': uom_id,
        }

InventoryLine()


class CompleteInventory(Wizard):
    'Complete Inventory'
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
        inventory_obj = self.pool.get('stock.inventory')
        inventory_obj.complete_lines(cursor, user, data['ids'], context=context)

        return {}

CompleteInventory()
