"Packing"
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import time

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class PackingIn(OSV):
    "Supplier Packing"
    _name = 'stock.packing.in'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True, states=STATES,
        domain="[('type', '=', 'warehouse')]",)
    incoming_moves = fields.One2Many(
        'stock.move', 'incoming_packing_in', 'Incoming Moves',
        states={'readonly': "state in ('received', 'done')",},
        context="{'warehouse': warehouse, 'packing_state': state, 'type':'incoming'}")
    inventory_moves = fields.One2Many(
        'stock.move', 'inventory_packing_in', 'Inventory Moves',
        states={'readonly': "state in ('draft', 'waiting')",},
        context="{'warehouse': warehouse, 'packing_state': state, 'type':'inventory_in'}")
    code = fields.Char("Code", size=None, select=1, readonly=True,)
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done'), ('cancel', 'Cancel'),
         ('waiting', 'Waiting'), ('received', 'Received')], 'State', readonly=True)

    def __init__(self):
        super(PackingIn, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            'set_state_received',
            'create_inventory_moves',
            ]
        self._order[0] = ('id', 'DESC')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.inventory_moves], context)
        self.write(
            cursor, user, packing_id,
            {'state':'done',
             'effective_date':time.strftime('%Y-%m-%d %H:%M:%S')},
            context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_cancel(
            cursor, user, [m.id for m in packing.incoming_moves] +\
            [m.id for m in packing.inventory_moves], context)
        self.write(cursor, user, packing_id, {'state':'cancel'},
                   context=context)

    def set_state_waiting(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_waiting(
            cursor, user, [m.id for m in packing.incoming_moves], context)
        self.write(cursor, user, packing_id, {'state':'waiting'},
                   context=context)

    def set_state_received(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.incoming_moves], context)
        self.write(
            cursor, user, packing_id, {'state':'received'}, context=context)
        self.create_inventory_moves(cursor, user, [packing_id], context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_draft(
            cursor, user, [m.id for m in packing.incoming_moves], context)
        move_obj.set_state_cancel(
            cursor, user, [m.id for m in packing.inventory_moves], context)
        self.write(cursor, user, packing_id, {'state':'draft'}, context=context)

    def create(self, cursor, user, values, context=None):
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.in')
        return super(PackingIn, self).create(
            cursor, user, values, context=context)

    def _store_location(self, cursor, user, incoming_move, context=None):
        return incoming_move.incoming_packing_in.warehouse.storage_location.id

    def create_inventory_moves(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        for packing in self.browse(cursor, user, ids, context=context):
            product_balance = {}
            for move in packing.inventory_moves:
                key = (move.product.id, move.uom.id, move.from_location.id)
                if key in product_balance:
                    product_balance[key] += move.quantity
                else:
                    product_balance[key] = move.quantity

            for move in packing.incoming_moves:
                key = (move.product.id, move.uom.id, move.to_location.id)
                if key in product_balance and \
                        product_balance[key] >= move.quantity:
                    product_balance[key] -= move.quantity
                else:
                    values = {
                        'product': move.product.id,
                        'uom': move.uom.id,
                        'quantity': move.quantity,
                        'from_location': move.to_location.id,
                        'to_location': self._store_location(
                            cursor, user, move, context=context),
                        'inventory_packing_in': packing.id,
                        'state': 'waiting',
                        }
                    move_obj.create(cursor, user, values, context=context)

PackingIn()


class PackingOut(OSV):
    "Customer Packing"
    _name = 'stock.packing.out'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        states={'readonly': "state != 'draft'",},
        domain="[('type', '=', 'warehouse')]",)
    customer_location = fields.Many2One(
        'stock.location', "Customer Location", required=True,
        states={'readonly': "state != 'draft'",},
        domain="[('type', '=', 'customer')]",)
    outgoing_moves = fields.One2Many(
        'stock.move', 'outgoing_packing_out', 'Outgoing Moves',
        states={'readonly':"state != 'ready'",},
        context="{'warehouse': warehouse, 'packing_state': state, 'type':'outgoing',}")
    inventory_moves = fields.One2Many(
        'stock.move', 'inventory_packing_out', 'Inventory Moves',
        states={'readonly':"state in ('ready', 'done')",},
        context="{'warehouse': warehouse, 'packing_state': state, 'type':'inventory_out',}")
    code = fields.Char("Code", size=None, select=1, readonly=True,)
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done'), ('cancel', 'Cancel'),
         ('assigned', 'Assigned'),('ready', 'Ready'), ('waiting', 'Waiting')],
        'State', readonly=True)

    def __init__(self):
        super(PackingOut, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            'set_state_assigned',
            'set_state_ready',
            'assign_try',
            'assign_force',
            ]
        self._order[0] = ('id', 'DESC')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def set_state_assigned(self, cursor, user, packing_id, context=None):
        self.write(cursor, user, packing_id, {'state':'assigned'},
                   context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.outgoing_moves],
            context=context)
        self.write(
            cursor, user, packing_id,
            {'state':'done', 'effective_date': time.strftime('%Y-%m-%d %H:%M:%S')},
            context=context)

    def set_state_ready(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.inventory_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'ready'},
                   context=context)
        for move in packing.inventory_moves:
            move_obj.create(cursor, user, {
                    'from_location': move.to_location.id,
                    'to_location': packing.customer_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': move.quantity,
                    'outgoing_packing_out': packing.id,
                    'state': 'waiting',
                    }, context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_cancel(
            cursor, user,[m.id for m in packing.outgoing_moves] +\
                [m.id for m in packing.inventory_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'cancel'},
                   context=context)

    def set_state_waiting(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_waiting(
            cursor, user, [m.id for m in packing.inventory_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'waiting'},
                   context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_draft(
            cursor, user, [m.id for m in packing.outgoing_moves],
            context=context)
        move_obj.set_state_cancel(
            cursor, user, [m.id for m in packing.inventory_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'draft'}, context=context)


    def create(self, cursor, user, values, context=None):
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.out')
        return super(PackingOut, self).create(cursor, user, values,
                                              context=context)

    def pick_product(self, cursor, user, total_qty, location_quantities,
                     product=None, location_index=None, context=None):
        """
        Pick the product across the location. Naive (fast)
        implementation.  Product is a browse record and location_index
        is the index of the browse record of all the locations.
        """
        to_pick = []
        for location,qty in location_quantities:
            if total_qty <= qty:
                to_pick.append((location, total_qty))
                return to_pick
            else:
                to_pick.append((location, qty))
                total_qty -= qty
        return False

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


    def assign_try(self, cursor, user, id, context=None):
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        packing = self.browse(cursor, user, id, context=context)
        parent_to_locations = {}
        inventory_moves = []
        uom_index = {}
        location_index = {}
        # Fetch child_of for each location
        for move in packing.inventory_moves:
            if move.state != 'waiting': continue
            inventory_moves.append(move)
            uom_index[move.uom.id] = move.uom
            location_index[move.from_location.id] = move.from_location
            if move.from_location.id in parent_to_locations:
                continue
            childs = location_obj.search(
                cursor, user, [('parent', 'child_of', [move.from_location.id])])
            parent_to_locations[move.from_location.id] = childs

        # Collect all raw quantities
        context = context or {}
        context.update({'in_states': ['done', 'assigned'],
                        'out_states': ['done', 'assigned']})
        raw_data = product_obj.raw_products_by_location(
            cursor, user,
            location_ids=reduce(
                lambda x,y:x+y, parent_to_locations.values(), []),
            product_ids=[move.product.id for move in inventory_moves],
            context=context)
        # convert raw data to something like:
        # {(location,product):[(qty,uom), ...],}
        processed_data = {}
        for line in raw_data:
            if line[:2] in processed_data:
                processed_data[line[:2]].append(line[2:])
            else:
                processed_data[line[:2]] = [line[2:]]
        success = True
        for move in inventory_moves:
            location_qties = []
            for location in parent_to_locations[move.from_location.id]:
                qty = self._location_amount(
                    cursor, user, move.uom.id,
                    processed_data[(move.from_location.id, move.product.id)],
                    uom_index, context=context,)
                location_qties.append((location, qty))

            to_pick = self.pick_product(
                cursor, user, move.quantity, location_qties,
                product=move.product, location_index=location_index,
                context=context)

            if to_pick == False:
                success = False
                continue

            first = True
            for location, qty in to_pick:
                values = {
                    'from_location': location,
                    'to_location': packing.warehouse.output_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': qty,
                    'inventory_packing_out': packing.id,
                    'state': 'assigned',
                    }
                if first:
                    move_obj.write(cursor, user, move.id, values,
                                   context=context)
                else:
                    move_obj.create(cursor, user, values, context=context)
                processed_data[(location, move.product.id)].append((move.uom.id, -qty))

        return success

    def assign_force(self, cursor, user, id, context=None):
        packing = self.browse(cursor, user, id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(cursor, user, [m.id for m in packing.inventory_moves], {'state':'assigned'})
        return True

PackingOut()
