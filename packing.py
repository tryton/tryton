"Packing"
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import time
from trytond.netsvc import LocalService
import datetime

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
    warehouse = fields.Many2One('stock.location', "Warehouse",
            required=True, states=STATES, domain="[('type', '=', 'warehouse')]")
    incoming_moves = fields.Function('get_incoming_moves', type='one2many',
            relation='stock.move', string='Incoming Moves',
            fnct_inv='set_incoming_moves',
            states={
                'readonly': "state in ('received', 'done')",
            }, context="{'warehouse': warehouse, "\
                    "'packing_state': state, 'type':'incoming'}")
    inventory_moves = fields.Function('get_inventory_moves', type='one2many',
            relation='stock.move', string='Inventory Moves',
            fnct_inv='set_inventory_moves',
            states={
                'readonly': "state == 'draft'",
            }, context="{'warehouse': warehouse, "\
                    "'packing_state': state, 'type':'inventory_in'}")
    moves = fields.One2Many('stock.move', 'packing_in', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(PackingIn, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._order[0] = ('id', 'DESC')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def get_incoming_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.to_location.id == packing.warehouse.input_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_incoming_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Incoming Moves must ' \
                                'have input location as destination location!')
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Incoming Moves must ' \
                                'have input location as destination location!')
            elif act[0] == 'add':
                move = move_obj.browse(cursor, user, act[1], context=context)
                if move.to_location.id != \
                        packing.warehouse.input_location.id:
                    raise ExceptORM('UserError', 'Incoming Moves must ' \
                            'have input location as destination location!')
            elif act[0] == 'set':
                moves = move_obj.browse(cursor, user, act[1], context=context)
                for move in moves:
                    if move.to_location.id != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Incoming Moves must ' \
                                'have input location as destination location!')
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.from_location.id == packing.warehouse.input_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have input location as source location!')
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have input location as source location!')
            elif act[0] == 'add':
                move = move_obj.browse(cursor, user, act[1], context=context)
                if move.from_location.id != \
                        packing.warehouse.input_location.id:
                    raise ExceptORM('UserError', 'Inventory Moves must ' \
                            'have input location as source location!')
            elif act[0] == 'set':
                moves = move_obj.browse(cursor, user, act[1], context=context)
                for move in moves:
                    if move.from_location.id != \
                            packing.warehouse.input_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have input location as source location!')
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(
            cursor, user, [m.id for m in packing.inventory_moves], context)
        self.write(cursor, user, packing_id,{
            'state': 'done',
            'effective_date': datetime.datetime.now(),
            }, context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_cancel(
            cursor, user, [m.id for m in packing.incoming_moves] +\
            [m.id for m in packing.inventory_moves], context)
        self.write(cursor, user, packing_id, {'state':'cancel'},
                   context=context)

    def set_state_received(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_done(cursor, user,
                [m.id for m in packing.incoming_moves], context=context)
        self.write(cursor, user, packing_id, {
            'state': 'received'
            }, context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.set_state_draft(
            cursor, user, [m.id for m in packing.incoming_moves], context)
        move_obj.set_state_waiting(
            cursor, user, [m.id for m in packing.incoming_moves], context)
        move_obj.unlink(
            cursor, user, [m.id for m in packing.inventory_moves], context)
        self.write(
            cursor, user, packing_id, {'state':'draft'}, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.in')
        return super(PackingIn, self).create(
            cursor, user, values, context=context)

    def _get_inventory_moves(self, cursor, user, incoming_move, context=None):
        res = {}
        if incoming_move.quantity <= 0.0:
            return None
        res['product'] = incoming_move.product.id
        res['uom'] = incoming_move.uom.id
        res['quantity'] = incoming_move.quantity
        res['from_location'] = incoming_move.to_location.id
        res['to_location'] = incoming_move.packing_in.warehouse.\
                storage_location.id
        res['state'] = 'waiting'
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, cursor, user, packing_id, context=None):
        packing = self.browse(cursor, user, packing_id, context=context)
        for incoming_move in packing.incoming_moves:
            vals = self._get_inventory_moves(cursor, user, incoming_move,
                    context=context)
            if vals:
                self.write(cursor, user, packing.id, {
                    'inventory_moves': [('create', vals)]
                    }, context=context)

    def button_draft(self, cursor, user, ids, context=None):
        workflow_service = LocalService('workflow')
        for packing in self.browse(cursor, user, ids, context=context):
            workflow_service.trg_create(user, self._name, packing.id, cursor)
        return True

PackingIn()


class PackingOut(OSV):
    "Customer Packing"
    _name = 'stock.packing.out'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
            states={
                'readonly': "state != 'draft'",
            }, domain="[('type', '=', 'warehouse')]")
    customer_location = fields.Many2One('stock.location', "Customer Location",
            required=True, states={
                'readonly': "state != 'draft'",
            }, domain="[('type', '=', 'customer')]")
    outgoing_moves = fields.Function('get_outgoing_moves', type='one2many',
            relation='stock.move', string='Outgoing Moves',
            fnct_inv='set_outgoing_moves',
            states={
                'readonly':"state != 'ready'",
            }, context="{'warehouse': warehouse, "\
                    "'packing_state': state, 'type':'outgoing',}")
    inventory_moves = fields.Function('get_inventory_moves', type='one2many',
            relation='stock.move', string='Inventory Moves',
            fnct_inv='set_inventory_moves',
            states={
                'readonly':"state in ('ready', 'done')",
            }, context="{'warehouse': warehouse, "\
                    "'packing_state': state, 'type':'inventory_out',}")
    moves = fields.One2Many('stock.move', 'packing_in', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('assigned', 'Assigned'),
        ('ready', 'Ready'),
        ('waiting', 'Waiting'),
        ], 'State', readonly=True)

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

    def get_outgoing_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.from_location.id == \
                        packing.warehouse.output_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_outgoing_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Outgoing Moves must ' \
                                'have output location as source location!')
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Outgoing Moves must ' \
                                'have output location as source location!')
            elif act[0] == 'add':
                move = move_obj.browse(cursor, user, act[1], context=context)
                if move.from_location.id != \
                        packing.warehouse.output_location.id:
                    raise ExceptORM('UserError', 'Outgoing Moves must ' \
                            'have output location as source location!')
            elif act[0] == 'set':
                moves = move_obj.browse(cursor, user, act[1], context=context)
                for move in moves:
                    if move.from_location.id != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Outgoing Moves must ' \
                                'have output location as source location!')
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.to_location.id == \
                        packing.warehouse.output_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have output location as destination location!')
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have output location as destination location!')
            elif act[0] == 'add':
                move = move_obj.browse(cursor, user, act[1], context=context)
                if move.to_location.id != \
                        packing.warehouse.output_location.id:
                    raise ExceptORM('UserError', 'Inventory Moves must ' \
                            'have output location as destination location!')
            elif act[0] == 'set':
                moves = move_obj.browse(cursor, user, act[1], context=context)
                for move in moves:
                    if move.to_location.id != \
                            packing.warehouse.output_location.id:
                        raise ExceptORM('UserError', 'Inventory Moves must ' \
                                'have output location as destination location!')
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

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
            {'state':'done',
             'effective_date': time.strftime('%Y-%m-%d %H:%M:%S')},
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
        self.write(
            cursor, user, packing_id, {'state':'draft'}, context=context)


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
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        packing = self.browse(cursor, user, id, context=context)
        parent_to_locations = {}
        inventory_moves = []
        uom_ids = uom_obj.search(cursor, user, [], context=context)
        uom_index = dict( (uom.id, uom) for uom in \
            uom_obj.browse(cursor, user, uom_ids, context=context))

        location_index = {}
        # Fetch child_of for each location
        for move in packing.inventory_moves:
            if move.state != 'waiting': continue
            inventory_moves.append(move)
            location_index[move.from_location.id] = move.from_location
            if move.from_location.id in parent_to_locations:
                continue
            childs = location_obj.search(
                cursor, user,
                [('parent', 'child_of', [move.from_location.id])])
            parent_to_locations[move.from_location.id] = childs

        # Collect all raw quantities
        context = context.copy()
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
                processed_data[
                    (location, move.product.id)].append((move.uom.id, -qty))

        return success

    def assign_force(self, cursor, user, id, context=None):
        packing = self.browse(cursor, user, id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(
            cursor, user, [m.id for m in packing.inventory_moves],
            {'state':'assigned'})
        return True

PackingOut()


class SelectMoveInit(WizardOSV):
    _name = 'stock.packing.in.select_move.init'
    moves = fields.Many2Many('stock.move', None, None, None, 'Moves',
            domain=[
                ('from_location.type', '=', 'supplier'),
                ('state', 'in', ['draft', 'waiting']),
                ('packing_in', '=', False),
            ])

    def fields_get(self, cursor, user, fields_names=None, context=None):
        packing_obj = self.pool.get('stock.packing.in')

        res = super(SelectMoveInit, self).fields_get(cursor, user,
                fields_names=fields_names, context=context)
        if 'moves' in res and context.get('active_id'):
            packing = packing_obj.browse(cursor, user, context['active_id'],
                    context=context)
            res['moves']['domain'].append(('to_location', '=',
                packing.warehouse.input_location.id))
        return res

SelectMoveInit()


class SelectMove(Wizard):
    'Select Moves'
    _name = 'stock.packing.in.select_move'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.packing.in.select_move.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('set', 'Ok', 'gtk-ok', True),
                ],
            },
        },
        'set': {
            'result': {
                'type': 'action',
                'action': '_action_set',
                'state': 'end',
            },
        },
    }


    def _action_set(self, cursor, user, datas, context=None):
        packing_obj = self.pool.get('stock.packing.in')

        packing_obj.write(cursor, user, datas['id'], {
            'incoming_moves': datas['form']['moves'],
            }, context=context)
        return {}

SelectMove()
