#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Packing"
from trytond.model import ModelWorkflow
from trytond.osv import fields, OSV
from trytond.report import CompanyReport
from trytond.wizard import Wizard, WizardOSV
from trytond.backend import TableHandler
import datetime

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class PackingIn(ModelWorkflow, OSV):
    "Supplier Packing"
    _name = 'stock.packing.in'
    _description = __doc__
    _rec_name = 'code'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date(
        'Planned Date', states={'readonly': "state != 'draft'",})
    reference = fields.Char(
        "Reference", size=None, select=1,
        states={'readonly': "state != 'draft'",})
    supplier = fields.Many2One('party.party', 'Supplier',
            states={
                'readonly': "state != 'draft' or bool(incoming_moves)",
            }, on_change=['supplier'], required=True)
    contact_address = fields.Many2One('party.address', 'Contact Address',
            states={
                'readonly': "state != 'draft'",
            }, domain="[('party', '=', supplier)]")
    warehouse = fields.Many2One('stock.location', "Warehouse",
            required=True, domain=[('type', '=', 'warehouse')],
            states={
                'readonly': "state in ('cancel', 'done') or " \
                        "bool(incoming_moves)",
            })
    incoming_moves = fields.Function('get_incoming_moves', type='one2many',
            relation='stock.move', string='Incoming Moves',
            fnct_inv='set_incoming_moves', add_remove="[" \
                "('packing_in', '=', False),"\
                "('from_location.type', '=', 'supplier'),"\
                "('state', '=', 'draft'),"\
                "('to_location_warehouse', '=', warehouse),"\
            "]",
            states={
                'readonly': "state in ('received', 'done', 'cancel') "\
                    "or not bool(warehouse)",
            }, context="{'warehouse': warehouse, 'type': 'incoming'," \
                    "'supplier': supplier}")
    inventory_moves = fields.Function('get_inventory_moves', type='one2many',
            relation='stock.move', string='Inventory Moves',
            fnct_inv='set_inventory_moves',
            states={
                'readonly': "state in ('draft', 'done', 'cancel')",
            }, context="{'warehouse': warehouse, 'type': 'inventory_in'}")
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
        self._error_messages.update({
            'incoming_move_input_dest': 'Incoming Moves must ' \
                    'have the warehouse input location as destination location!',
            'inventory_move_input_source': 'Inventory Moves must ' \
                    'have the warehouse input location as source location!',
            })

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
                    context=context)[0]
        return False

    def on_change_supplier(self, cursor, user, ids, values, context=None):
        if not values.get('supplier'):
            return {'contact_address': False}
        party_obj = self.pool.get("party.party")
        address_id = party_obj.address_get(cursor, user, values['supplier'],
                                          context=context)
        return {'contact_address': address_id}

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

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    packing.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'incoming_move_input_dest', context=context)

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

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    packing.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_input_source', context=context)

        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.inventory_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context)
        self.write(cursor, user, packing_id,{
            'state': 'done',
            'effective_date': datetime.date.today(),
            }, context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.incoming_moves \
                 if m.state != 'cancel'] +\
            [m.id for m in packing.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context)
        self.write(cursor, user, packing_id, {'state': 'cancel'},
                   context=context)

    def set_state_received(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.incoming_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, packing_id, {
            'state': 'received'
            }, context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(cursor, user, [m.id for m in packing.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            }, context=context)
        move_obj.delete(cursor, user,
                [m.id for m in packing.inventory_moves], context=context)
        self.write(cursor, user, packing_id, {
            'state': 'draft',
            }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.in', context=context)
        return super(PackingIn, self).create(
            cursor, user, values, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(PackingIn, self).copy(cursor, user, ids,
                default=default, context=context)

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
        res['state'] = 'draft'
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
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

PackingIn()


class PackingInReturn(ModelWorkflow, OSV):
    "Supplier Return Packing"
    _name = 'stock.packing.in.return'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date(
        'Planned Date', states={'readonly': "state != 'draft'",})
    code = fields.Char("Code", size=None, select=1, readonly=True)
    reference = fields.Char(
        "Reference", size=None, select=1,
        states={'readonly': "state != 'draft'",})
    from_location = fields.Many2One(
        'stock.location', "From Location", required=True,
        states={ 'readonly': "state != 'draft' or bool(moves)", },
        domain=[('type', '=', 'storage')])
    to_location = fields.Many2One('stock.location', "To Location",
            required=True, states={
                'readonly': "state != 'draft' or bool(moves)",
            }, domain=[('type', '=', 'supplier')])
    moves = fields.One2Many(
        'stock.move', 'packing_in_return', 'Moves',
        states={'readonly': "state != 'draft' or "\
                    "not(bool(from_location) and bool (to_location))"},
        context="{'from_location': from_location,"
                "'to_location': to_location,"
                "'planned_date': planned_date}",
        )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

    def __init__(self):
        super(PackingInReturn, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._order[0] = ('id', 'DESC')

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.in.return', context=context)
        return super(PackingInReturn, self).create(
            cursor, user, values, context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.moves if m.state != 'draft'],
            {'state': 'draft'}, context=context)

    def set_state_waiting(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.moves if m.state not in ('cancel', 'draft')],
            {'state': 'draft', 'planned_date': packing.planned_date,},
            context=context)

        self.write(
            cursor, user, packing_id, {'state': 'waiting'}, context=context)

    def set_state_assigned(self, cursor, user, packing_id, context=None):
        self.write(
            cursor, user, packing_id, {'state': 'assigned'}, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.moves if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, packing_id,
                    {'state': 'done',
                     'effective_date': datetime.date.today()},
                    context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.moves if m.state != 'cancel'],
            {'state': 'cancel'}, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'cancel'}, context=context)

    def assign_try(self, cursor, user, packing_id, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        date_obj = self.pool.get('ir.date')

        packing = self.browse(cursor, user, packing_id, context=context)

        cursor.execute('LOCK TABLE stock_move')

        local_ctx = context and context.copy() or {}
        local_ctx['stock_date_end'] = date_obj.today(cursor, user,
                context=context)
        local_ctx['stock_assign'] = True
        location_ids = [m.from_location.id for m in packing.moves]
        pbl = product_obj.products_by_location(cursor, user,
            location_ids=location_ids,
            product_ids=[m.product.id for m in packing.moves],
            context=local_ctx)

        for move in packing.moves:
            if move.state != 'draft':
                continue
            if (move.from_location.id, move.product.id) in pbl:
                qty_default_uom = pbl[(move.from_location.id, move.product.id)]
                qty = uom_obj.compute_qty(
                    cursor, user, move.product.default_uom, qty_default_uom,
                    move.uom, round=False, context=context)
                if qty < move.quantity:
                    return False
                pbl[(move.from_location.id, move.product.id)] = \
                    pbl[(move.from_location.id, move.product.id)] - qty_default_uom

        move_obj.write(cursor, user, [m.id for m in packing.moves],
                       {'state': 'assigned'}, context=context)
        return True

    def assign_force(self, cursor, user, packing_id, context=None):
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(cursor, user, [m.id for m in packing.moves], {
            'state': 'assigned',
            }, context=context)
        return True


PackingInReturn()


class PackingOut(ModelWorkflow, OSV):
    "Customer Packing"
    _name = 'stock.packing.out'
    _description = __doc__
    _rec_name = 'code'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date',
            states={
                'readonly': "state != 'draft'",
            })
    customer = fields.Many2One('party.party', 'Customer', required=True,
            states={
                'readonly': "state != 'draft' or bool(outgoing_moves)",
            }, on_change=['customer'])
    delivery_address = fields.Many2One('party.address',
            'Delivery Address', required=True,
            states={
                'readonly': "state != 'draft'",
            }, domain="[('party', '=', customer)]")
    reference = fields.Char("Reference", size=None, select=1,
            states={
                'readonly': "state != 'draft'",
            })
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
            states={
                'readonly': "state != 'draft' or bool(outgoing_moves)",
            }, domain=[('type', '=', 'warehouse')])
    outgoing_moves = fields.Function('get_outgoing_moves', type='one2many',
            relation='stock.move', string='Outgoing Moves',
            fnct_inv='set_outgoing_moves',
            states={
                'readonly':"state != 'draft' or not bool(warehouse)",
            }, context="{'warehouse': warehouse, 'type': 'outgoing'," \
                    "'customer': customer}")
    inventory_moves = fields.Function('get_inventory_moves', type='one2many',
            relation='stock.move', string='Inventory Moves',
            fnct_inv='set_inventory_moves',
            states={
                'readonly':"state in ('draft', 'packed', 'done')",
            }, context="{'warehouse': warehouse, 'type': 'inventory_out',}")
    moves = fields.One2Many('stock.move', 'packing_out', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('assigned', 'Assigned'),
        ('packed', 'Packed'),
        ('waiting', 'Waiting'),
        ], 'State', readonly=True)

    def __init__(self):
        super(PackingOut, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._order[0] = ('id', 'DESC')

    def init(self, cursor, module_name):
        super(PackingOut, self).init(cursor, module_name)
        table = TableHandler(cursor, self._table, self._name, module_name)

        # Migration from 1.0 customer_location is no more used
        table.drop_column('customer_location', exception=True)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
                    context=context)[0]
        return False

    def on_change_customer(self, cursor, user, ids, values, context=None):
        if not values.get('customer'):
            return {'delivery_address': False}
        party_obj = self.pool.get("party.party")
        address_id = party_obj.address_get(cursor, user, values['customer'],
                type='delivery', context=context)
        return {
                'delivery_address': address_id}

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

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            packing.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'outgoing_move_output_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            packing.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'outgoing_move_output_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    packing.warehouse.output_location.id:
                self.raise_user_error(cursor,
                        'outgoing_move_output_source', context=context)
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

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            packing.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_output_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            packing.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_output_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    packing.warehouse.output_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_output_dest', context=context)
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def set_state_assigned(self, cursor, user, packing_id, context=None):
        self.write(cursor, user, packing_id, {'state': 'assigned'},
                   context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.inventory_moves + packing.outgoing_moves \
                 if m.state != 'draft'],
            {'state': 'draft'}, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.outgoing_moves \
                               if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, packing_id, {
            'state': 'done',
            'effective_date': datetime.date.today(),
            }, context=context)

    def set_state_packed(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.inventory_moves \
                               if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, packing_id, {'state': 'packed'},
                   context=context)
        # Sum all outgoing quantities
        outgoing_qty = {}
        for move in packing.outgoing_moves:
            if move.state == 'cancel': continue
            quantity = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                context=context)
            outgoing_qty.setdefault(move.product.id, 0.0)
            outgoing_qty[move.product.id] += quantity

        for move in packing.inventory_moves:
            if move.state == 'cancel': continue
            qty_default_uom = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                context=context)
            # Check if the outgoing move doesn't exist already
            if outgoing_qty.get(move.product.id):
                # If it exist, decrease the sum
                if qty_default_uom <= outgoing_qty[move.product.id]:
                    outgoing_qty[move.product.id] -= qty_default_uom
                    continue
                # Else create the complement
                else:
                    out_quantity = qty_default_uom - outgoing_qty[move.product.id]
                    out_quantity = uom_obj.compute_qty(
                        cursor, user, move.product.default_uom, out_quantity,
                        move.uom, context=context)
                    outgoing_qty[move.product.id] = 0.0
            else:
                out_quantity = move.quantity

            unit_price = uom_obj.compute_price(
                cursor, user, move.product.default_uom, move.product.list_price,
                move.uom, context=context)
            move_obj.create(cursor, user, {
                    'from_location': move.to_location.id,
                    'to_location': packing.customer.customer_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': out_quantity,
                    'packing_out': packing.id,
                    'state': 'draft',
                    'company': move.company.id,
                    'currency': move.company.currency.id,
                    'unit_price': unit_price,
                    }, context=context)

        #Re-read the packing and remove exceeding quantities
        packing = self.browse(cursor, user, packing_id, context=context)
        for move in packing.outgoing_moves:
            if move.state == 'cancel': continue
            if outgoing_qty.get(move.product.id, 0.0) > 0.0:
                exc_qty = uom_obj.compute_qty(
                    cursor, user, move.product.default_uom,
                    outgoing_qty[move.product.id], move.uom, context=context)
                move_obj.write(cursor, user, move.id,{
                    'quantity': max(0.0, move.quantity-exc_qty),
                    }, context=context)
                removed_qty = uom_obj.compute_qty(
                    cursor, user, move.uom, min(exc_qty, move.quantity),
                    move.product.default_uom, context=context)
                outgoing_qty[move.product.id] -= removed_qty

        move_obj.write(cursor, user, [x.id for x in packing.outgoing_moves
            if x.state != 'cancel'], {
                'state': 'assigned',
                }, context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.outgoing_moves + packing.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context=context)
        self.write(cursor, user, packing_id, {'state': 'cancel'},
                   context=context)

    def set_state_waiting(self, cursor, user, packing_id, context=None):
        """
        Complete inventory moves to match the products and quantities
        that are in the outgoing moves.
        """
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        packing = self.browse(cursor, user, packing_id, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'waiting'}, context=context)

        if packing.inventory_moves:
            move_obj.write(cursor, user,
                    [x.id for x in packing.inventory_moves], {
                        'state': 'draft',
                        }, context=context)
            move_obj.delete(cursor, user,
                    [x.id for x in packing.inventory_moves], context=context)

            # Re-Browse because moves have been deleted
            packing = self.browse(cursor, user, packing_id, context=context)

        for move in packing.outgoing_moves:
            if move.state in ('cancel', 'done'):
                continue
            qty_default_uom = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                context=context)
            move_obj.create(cursor, user, {
                    'from_location': move.packing_out.warehouse.storage_location.id,
                    'to_location': move.from_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': move.quantity,
                    'packing_out': packing.id,
                    'state': 'draft',
                    'company': move.company.id,
                    }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.out', context=context)
        return super(PackingOut, self).create(cursor, user, values,
                context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['outgoing_moves']= False
        return super(PackingOut, self).copy(cursor, user, ids,
                default=default, context=context)


    def _location_amount(self, cursor, user, target_uom,
            qty_uom, uom_index, context=None):
        """
        Take a raw list of quantities and uom and convert it to
        the target uom.
        """
        uom_obj = self.pool.get('product.uom')
        res = 0
        for uom, qty in qty_uom:
            res += uom_obj.compute_qty(
                cursor, user, uom_index[uom], qty, uom_index[target_uom],
                context=context)
        return res

    def assign_try(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        return move_obj.assign_try(
            cursor, user, packing.inventory_moves, context=context)

    def assign_force(self, cursor, user, packing_id, context=None):
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(
            cursor, user, [m.id for m in packing.inventory_moves],
            {'state': 'assigned'})
        return True

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)

PackingOut()



class PackingOutReturn(ModelWorkflow, OSV):
    "Customer Return Packing"
    _name = 'stock.packing.out.return'
    _description = __doc__
    _rec_name = 'code'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date',
            states={
                'readonly': "state != 'draft'",
            })
    customer = fields.Many2One('party.party', 'Customer', required=True,
            states={
                'readonly': "state != 'draft' or bool(incoming_moves)",
            }, on_change=['customer'])
    delivery_address = fields.Many2One('party.address',
            'Delivery Address', required=True,
            states={
                'readonly': "state != 'draft'",
            }, domain="[('party', '=', customer)]")
    reference = fields.Char("Reference", size=None, select=1,
            states={
                'readonly': "state != 'draft'",
            })
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
            states={
                'readonly': "state != 'draft' or bool(incoming_moves)",
            }, domain=[('type', '=', 'warehouse')])
    incoming_moves = fields.Function('get_incoming_moves', type='one2many',
            relation='stock.move', string='Incoming Moves',
            fnct_inv='set_incoming_moves',
            states={
                'readonly':"state != 'draft'",
            }, context="{'warehouse': warehouse, 'type': 'incoming'," \
                    "'customer': customer}")
    inventory_moves = fields.Function('get_inventory_moves', type='one2many',
            relation='stock.move', string='Inventory Moves',
            fnct_inv='set_inventory_moves',
            states={
                'readonly':"state in ('draft', 'cancel', 'done')",
            }, context="{'warehouse': warehouse, 'type': 'inventory_out',}")
    moves = fields.One2Many('stock.move', 'packing_out_return', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(PackingOutReturn, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'incoming_move_input_dest': 'Incoming Moves must ' \
                    'have the warehouse input location as destination location!',
            'inventory_move_input_source': 'Inventory Moves must ' \
                    'have the warehouse input location as source location!',
            })


    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
                    context=context)[0]
        return False

    def on_change_customer(self, cursor, user, ids, values, context=None):
        if not values.get('customer'):
            return {'delivery_address': False}
        party_obj = self.pool.get("party.party")
        address_id = party_obj.address_get(cursor, user, values['customer'],
                type='delivery', context=context)
        party = party_obj.browse(cursor, user, values['customer'], context=context)
        return {
                'delivery_address': address_id,
            }

    def get_incoming_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.to_location.id == \
                        packing.warehouse.input_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_incoming_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    packing.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'incoming_move_input_dest', context=context)
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for packing in self.browse(cursor, user, ids, context=context):
            res[packing.id] = []
            for move in packing.moves:
                if move.from_location.id == \
                        packing.warehouse.input_location.id:
                    res[packing.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, packing_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        packing = self.browse(cursor, user, packing_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            packing.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    packing.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_input_source', context=context)
        self.write(cursor, user, packing_id, {
            'moves': value,
            }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.out.return', context=context)
        return super(PackingOutReturn, self).create(cursor, user, values,
                context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(PackingOutReturn, self).copy(cursor, user, ids,
                default=default, context=context)


    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.inventory_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context)
        self.write(cursor, user, packing_id,{
            'state': 'done',
            'effective_date': datetime.date.today(),
            }, context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.incoming_moves + packing.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context)
        self.write(cursor, user, packing_id, {'state': 'cancel'},
                   context=context)

    def set_state_received(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in packing.incoming_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, packing_id, {
            'state': 'received'
            }, context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(cursor, user, [m.id for m in packing.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            }, context=context)
        move_obj.delete(cursor, user,
                [m.id for m in packing.inventory_moves], context=context)
        self.write(cursor, user, packing_id, {
            'state': 'draft',
            }, context=context)

    def _get_inventory_moves(self, cursor, user, incoming_move, context=None):
        res = {}
        if incoming_move.quantity <= 0.0:
            return None
        res['product'] = incoming_move.product.id
        res['uom'] = incoming_move.uom.id
        res['quantity'] = incoming_move.quantity
        res['from_location'] = incoming_move.to_location.id
        res['to_location'] = incoming_move.packing_out_return.warehouse.\
                storage_location.id
        res['state'] = 'draft'
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

PackingOutReturn()


class AssignPackingOutAskForce(WizardOSV):
    'Assign Packing Out Ask Force'
    _name = 'stock.packing.out.assign.ask_force'
    _description = __doc__

    inventory_moves = fields.Many2Many('stock.move', None, None, None,
            'Inventory Moves', readonly=True)

AssignPackingOutAskForce()


class AssignPackingOut(Wizard):
    'Assign Packing Out'
    _name = 'stock.packing.out.assign'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.packing.out.assign.ask_force',
                'state': [
                    ('force', 'Force Assign', 'tryton-go-next'),
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'force': {
            'result': {
                'type': 'action',
                'action': '_force',
                'state': 'end',
            },
        },
    }

    def _choice(self, cursor, user, data, context=None):
        packing_out_obj = self.pool.get('stock.packing.out')

        packing_out_obj.workflow_trigger_validate(cursor, user, data['id'],
                'assign', context=context)
        packing = packing_out_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in packing.inventory_moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        packing_out_obj = self.pool.get('stock.packing.out')
        packing = packing_out_obj.browse(cursor, user, data['id'],
                context=context)
        return {'inventory_moves': [x.id for x in packing.inventory_moves
            if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        packing_out_obj = self.pool.get('stock.packing.out')

        packing_out_obj.workflow_trigger_validate(cursor, user, data['id'],
                'force_assign', context=context)
        return {}

AssignPackingOut()


class PackingInternal(ModelWorkflow, OSV):
    "Internal Packing"
    _name = 'stock.packing.internal'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date(
        'Planned Date', states={'readonly': "state != 'draft'",})
    code = fields.Char("Code", size=None, select=1, readonly=True)
    reference = fields.Char(
        "Reference", size=None, select=1,
        states={'readonly': "state != 'draft'",})
    from_location = fields.Many2One(
        'stock.location', "From Location", required=True,
        states={ 'readonly': "state != 'draft' or bool(moves)", },
        domain="[('type', 'not in', " \
                    "('supplier', 'customer', 'warehouse', 'view'))]")
    to_location = fields.Many2One('stock.location', "To Location",
            required=True, states={
                'readonly': "state != 'draft' or bool(moves)",
            }, domain="[('type', 'not in', " \
                    "('supplier', 'customer', 'warehouse', 'view'))]")
    moves = fields.One2Many(
        'stock.move', 'packing_internal', 'Moves',
        states={'readonly': "state != 'draft' or "\
                    "not(bool(from_location) and bool (to_location))"},
        context="{'from_location': from_location,"
                "'to_location': to_location,"
                "'planned_date': planned_date}",
        )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

    def __init__(self):
        super(PackingInternal, self).__init__()
        self._rpc_allowed += [
            'button_draft',
        ]
        self._order[0] = ('id', 'DESC')

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.packing.internal', context=context)
        return super(PackingInternal, self).create(
            cursor, user, values, context=context)

    def set_state_draft(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.moves], {'state': 'draft'},
            context=context)

    def set_state_waiting(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(cursor, user, [m.id for m in packing.moves], {
            'from_location': packing.from_location.id,
            'to_location': packing.to_location.id,
            'state': 'draft',
            'planned_date': packing.planned_date,
            }, context=context)
        self.write(
            cursor, user, packing_id, {'state': 'waiting'}, context=context)

    def set_state_assigned(self, cursor, user, packing_id, context=None):
        self.write(
            cursor, user, packing_id, {'state': 'assigned'}, context=context)

    def set_state_done(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.moves], {'state': 'done'},
            context=context)
        self.write( cursor, user, packing_id,
                    {'state': 'done',
                     'effective_date': datetime.date.today()},
                    context=context)

    def set_state_cancel(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in packing.moves], {'state': 'cancel'},
            context=context)
        self.write(
            cursor, user, packing_id, {'state': 'cancel'}, context=context)

    def assign_try(self, cursor, user, packing_id, context=None):
        move_obj = self.pool.get('stock.move')
        packing = self.browse(cursor, user, packing_id, context=context)
        return move_obj.assign_try(
            cursor, user, packing.moves, context=context)

    def assign_force(self, cursor, user, packing_id, context=None):
        packing = self.browse(cursor, user, packing_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(cursor, user, [m.id for m in packing.moves], {
            'state': 'assigned',
            }, context=context)
        return True

PackingInternal()


class Address(OSV):
    _name = 'party.address'
    delivery = fields.Boolean('Delivery')

Address()


class AssignPackingInternalAskForce(WizardOSV):
    'Assign Packing Internal Ask Force'
    _name = 'stock.packing.internal.assign.ask_force'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, None, 'Moves',
            readonly=True)

AssignPackingInternalAskForce()


class AssignPackingInternal(Wizard):
    'Assign Packing Internal'
    _name = 'stock.packing.internal.assign'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.packing.internal.assign.ask_force',
                'state': [
                    ('force', 'Force Assign', 'tryton-go-next'),
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'force': {
            'result': {
                'type': 'action',
                'action': '_force',
                'state': 'end',
            },
        },
    }

    def _choice(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.internal')

        packing_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'assign', context=context)
        packing = packing_internal_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in packing.moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.internal')
        packing = packing_internal_obj.browse(cursor, user, data['id'],
                context=context)
        return {'moves': [x.id for x in packing.moves if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.internal')

        packing_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'force_assign', context=context)
        return {}

AssignPackingInternal()


class AssignPackingInReturnAskForce(WizardOSV):
    'Assign Supplier Return Packing Ask Force'
    _name = 'stock.packing.in.return.assign.ask_force'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, None, 'Moves',
            readonly=True)

AssignPackingInReturnAskForce()


class AssignPackingInReturn(Wizard):
    'Assign Supplier Return Packing'
    _name = 'stock.packing.in.return.assign'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.packing.in.return.assign.ask_force',
                'state': [
                    ('force', 'Force Assign', 'tryton-go-next'),
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'force': {
            'result': {
                'type': 'action',
                'action': '_force',
                'state': 'end',
            },
        },
    }

    def _choice(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.in.return')

        packing_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'assign', context=context)
        packing = packing_internal_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in packing.moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.in.return')
        packing = packing_internal_obj.browse(cursor, user, data['id'],
                context=context)
        return {'moves': [x.id for x in packing.moves if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        packing_internal_obj = self.pool.get('stock.packing.in.return')

        packing_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'force_assign', context=context)
        return {}

AssignPackingInReturn()


class CreatePackingOutReturn(Wizard):
    'Create Customer Return Packing'
    _name = 'stock.packing.out.return.create'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_create',
                'state': 'end',
                },
            },
        }
    def __init__(self):
        super(CreatePackingOutReturn, self).__init__()
        self._error_messages.update({
            'packing_done_title': 'You can not create return packing',
            'packing_done_msg': 'The packing with code %s is not yet sent.',
            })


    def _create(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        packing_out_obj = self.pool.get('stock.packing.out')
        packing_out_return_obj = self.pool.get('stock.packing.out.return')

        packing_outs = packing_out_obj.browse(
            cursor, user, data['ids'], context=context)

        packing_out_return_ids = []
        for packing_out in packing_outs:
            if packing_out.state != 'done':
                self.raise_user_error(
                    cursor, 'packing_done_title',
                    error_description='packing_done_msg',
                    error_description_args=packing_out.code,
                    context=context)

            incoming_moves = []
            for move in packing_out.outgoing_moves:
                incoming_moves.append(('create', {
                            'product': move.product.id,
                            'quantity': move.quantity,
                            'uom': move.uom.id,
                            'from_location': move.to_location.id,
                            'to_location': packing_out.warehouse.input_location.id,
                            'company': move.company.id,
                            }))
            packing_out_return_ids.append(
                packing_out_return_obj.create(
                    cursor, user,
                    {'customer': packing_out.customer.id,
                     'delivery_address': packing_out.delivery_address.id,
                     'warehouse': packing_out.warehouse.id,
                     'incoming_moves': incoming_moves,
                     },
                    context=context)
                )

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_packing_out_return_form'),
            ('module', '=', 'stock'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['res_id'] = packing_out_return_ids
        if len(packing_out_return_ids) == 1:
            res['views'].reverse()

        return res

CreatePackingOutReturn()


class PackingOutReport(CompanyReport):
    _name = 'stock.packing.out'

    def parse(self, cursor, user, report, objects, datas, context):
        if context is None:
            context = {}
        context = context.copy()
        context['product_name'] = lambda product_id, language: \
                self.product_name(cursor, user, product_id, language,
                        context)
        return super(PackingOutReport, self).parse(cursor, user, report,
                objects, datas, context)

    def product_name(self, cursor, user, product_id, language, context):
        product_obj = self.pool.get('product.product')
        ctx = context.copy()
        ctx['language'] = language
        return product_obj.name_get(cursor, user, [product_id],
                context=ctx)[0][1]

PackingOutReport()
