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
    _order = 'id DESC'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.warehouse',"Warehouse", required=True, states=STATES,)
    incoming_moves = fields.One2Many(
        'stock.move', 'incoming_packing_in', 'Incoming Moves',
        states={'readonly':"state in ('received','done')",},
        context="{'wh_incoming': warehouse, 'pack_incoming_state': state}")
    inventory_moves = fields.One2Many(
        'stock.move', 'inventory_packing_in', 'Inventory Moves',
        states={'readonly':"state in ('draft','waiting')",},
        context="{'wh_inv_in': warehouse, 'pack_inv_in_state': state}")
    code = fields.Char("Code", size=None, select=1, readonly=True,)
    state = fields.Selection(
        [('draft','Draft'),('done','Done'),('cancel','Cancel'),
         ('waiting','Waiting'),('received','Received')], 'State', readonly=True)


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

    def create_inventory_moves(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        for packing in self.browse(cursor, user, ids, context=context):
            product_balance = {}
            for move in packing.incoming_moves:
                key = (move.product.id, move.uom.id, move.to_location.id)
                if key in product_balance:
                    product_balance[key] += move.quantity
                else:
                    product_balance[key] = move.quantity

            for move in packing.inventory_moves:
                key = (move.product.id, move.uom.id, move.from_location.id)
                if key in product_balance:
                    product_balance[key] -= move.quantity
                else:
                    product_balance[key] = -move.quantity

            for (product,uom,location),quantity in product_balance.iteritems():
                if quantity>0:
                    values = {
                        'product': product,
                        'uom': uom,
                        'quantity': quantity,
                        'from_location':location,
                        'to_location': packing.warehouse.store_location.id,
                        'inventory_packing_in': packing.id,
                        'state': 'waiting',
                        }
                    move_obj.create(cursor, user, values, context=context)

PackingIn()


class PackingOut(OSV):
    "Customer Packing"
    _name = 'stock.packing.out'
    _order = 'id DESC'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    warehouse = fields.Many2One(
        'stock.warehouse',"Warehouse", required=True, states=STATES,)
    outgoing_moves = fields.One2Many(
        'stock.move', 'outgoing_packing_out', 'Outgoing Moves',
        states=STATES,
        context="{'wh_outgoing': warehouse, 'pack_outgoing_state': state}")
    inventory_moves = fields.One2Many(
        'stock.move', 'inventory_packing_out', 'Inventory Moves',
        states={'readonly':"state not in ('assigned')",},
        context="{'wh_inv_out': warehouse, 'pack_inv_out_state': state}")
    code = fields.Char("Code", size=None, select=1, readonly=True,)
    state = fields.Selection(
        [('draft','Draft'),('done','Done'),('cancel','Cancel'),
         ('ready','Ready'), ('assigned','Assigned'),('waiting','Waiting')],
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

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.outgoing_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'done'}, context=context)

    def set_state_ready(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.inventory_moves],
            context=context)
        self.write(cursor, user, packing_id, {'state':'ready'},
                   context=context)

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
            cursor, user, [m.id for m in packing.outgoing_moves],
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

    def set_state_assigned(self, cursor, user, packing_id, context=None):
        self.write(cursor, user, packing_id, {'state':'assigned'}, context=context)

    def create(self, cursor, user, values, context=None):
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.out')
        return super(PackingOut, self).create(cursor, user, values,
                                              context=context)


    def pick_product(self, cursor, user, product, quantity, uom, locations, context=None):
        """
        Pick the product across the location. Naive (fast) implementation.
        """


    def assign_try(self, cursor, user, id, context=None):
        """
        Try to assign products for a given customer packing.
        """

        location_obj = self.pool.get('stock.location')
        packing = self.browse(cursor, user, id, context=context)
        if not packing.outgoing_moves:
            return False
        product_ids = [m.product.id for m in packing.outgoing_moves]
        location_ids = [l.id for l in packing.warehouse.locations]

        print location_obj.products_by_location(
            cursor, user, location_ids, product_ids, context=context)


        return False #True

    def assign_force(self, cursor, user, id, context=None):
        return True

PackingOut()
