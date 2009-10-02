#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Shipment"
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class ShipmentIn(ModelWorkflow, ModelSQL, ModelView):
    "Supplier Shipment"
    _name = 'stock.shipment.in'
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
                'readonly': "(state != 'draft' or bool(incoming_moves)) " \
                        "and bool(supplier)",
            }, on_change=['supplier'], required=True)
    contact_address = fields.Many2One('party.address', 'Contact Address',
            states={
                'readonly': "state != 'draft'",
            }, domain=["('party', '=', supplier)"])
    warehouse = fields.Many2One('stock.location', "Warehouse",
            required=True, domain=[('type', '=', 'warehouse')],
            states={
                'readonly': "state in ('cancel', 'done') or " \
                        "bool(incoming_moves)",
            })
    incoming_moves = fields.Function('get_incoming_moves', type='one2many',
            relation='stock.move', string='Incoming Moves',
            fnct_inv='set_incoming_moves', add_remove="[" \
                "('shipment_in', '=', False),"\
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
    moves = fields.One2Many('stock.move', 'shipment_in', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentIn, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'incoming_move_input_dest': 'Incoming Moves must ' \
                    'have the warehouse input location as destination location!',
            'inventory_move_input_source': 'Inventory Moves must ' \
                    'have the warehouse input location as source location!',
            })

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "\
                "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "\
                "WHERE fs_id like '%%packing%%' AND module = %s",
                (module_name,))
        cursor.execute("UPDATE ir_model "\
                "SET model = REPLACE(model, 'packing', 'shipment') "\
                "WHERE model like '%%packing%%' AND module = %s",
                (module_name,))
        cursor.execute("UPDATE ir_model_field "\
                "SET relation = REPLACE(relation, 'packing', 'shipment'), "\
                    "name = REPLACE(name, 'packing', 'shipment') "
                "WHERE (relation like '%%packing%%' "\
                    "OR name like '%%packing%%') AND module = %s",
                (module_name,))

        cursor.execute("UPDATE wkf "\
                "SET model = 'stock.shipment.in' "\
                "where model = 'stock.packing.in'")
        cursor.execute("UPDATE wkf_instance "\
                "SET res_type = 'stock.shipment.in' "\
                "where res_type = 'stock.packing.in'")
        cursor.execute("UPDATE wkf_trigger "\
                "SET model = 'stock.shipment.in' "\
                "WHERE model = 'stock.packing.in'")

        old_table = 'stock_packing_in'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, self._table)
        table = TableHandler(cursor, self, module_name)
        for field in ('create_uid', 'write_uid', 'contact_address',
                'warehouse', 'supplier'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        super(ShipmentIn, self).init(cursor, module_name)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
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
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_incoming_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    shipment.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'incoming_move_input_dest', context=context)

        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    shipment.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_input_source', context=context)

        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def set_state_done(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        date_obj = self.pool.get('ir.date')

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.inventory_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context)
        self.write(cursor, user, shipment_id,{
            'state': 'done',
            'effective_date': date_obj.today(cursor, user, context=context),
            }, context=context)

    def set_state_cancel(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.incoming_moves \
                 if m.state != 'cancel'] +\
            [m.id for m in shipment.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context)
        self.write(cursor, user, shipment_id, {'state': 'cancel'},
                   context=context)

    def set_state_received(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.incoming_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'received'
            }, context=context)

    def set_state_draft(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(cursor, user, [m.id for m in shipment.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            }, context=context)
        move_obj.delete(cursor, user,
                [m.id for m in shipment.inventory_moves], context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'draft',
            }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.shipment.in', context=context)
        return super(ShipmentIn, self).create(
            cursor, user, values, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(ShipmentIn, self).copy(cursor, user, ids,
                default=default, context=context)

    def _get_inventory_moves(self, cursor, user, incoming_move, context=None):
        res = {}
        if incoming_move.quantity <= 0.0:
            return None
        res['product'] = incoming_move.product.id
        res['uom'] = incoming_move.uom.id
        res['quantity'] = incoming_move.quantity
        res['from_location'] = incoming_move.to_location.id
        res['to_location'] = incoming_move.shipment_in.warehouse.\
                storage_location.id
        res['state'] = 'draft'
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, cursor, user, shipment_id, context=None):
        shipment = self.browse(cursor, user, shipment_id, context=context)
        for incoming_move in shipment.incoming_moves:
            vals = self._get_inventory_moves(cursor, user, incoming_move,
                    context=context)
            if vals:
                self.write(cursor, user, shipment.id, {
                    'inventory_moves': [('create', vals)]
                    }, context=context)

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

ShipmentIn()


class ShipmentInReturn(ModelWorkflow, ModelSQL, ModelView):
    "Supplier Return Shipment"
    _name = 'stock.shipment.in.return'
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
        'stock.move', 'shipment_in_return', 'Moves',
        states={'readonly': "state != 'draft' or "\
                    "not(bool(from_location) and bool (to_location))"},
        context="{'from_location': from_location,"
                "'to_location': to_location,"
                "'planned_date': planned_date}",
        )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE wkf "\
                "SET model = 'stock.shipment.in.return' "\
                "where model = 'stock.packing.in.return'")
        cursor.execute("UPDATE wkf_instance "\
                "SET res_type = 'stock.shipment.in.return' "\
                "where res_type = 'stock.packing.in.return'")
        cursor.execute("UPDATE wkf_trigger "\
                "SET model = 'stock.shipment.in.return' "\
                "WHERE model = 'stock.packing.in.return'")

        old_table = 'stock_packing_in_return'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, self._table)
        table = TableHandler(cursor, self, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        super(ShipmentInReturn, self).init(cursor, module_name)

    def __init__(self):
        super(ShipmentInReturn, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.shipment.in.return', context=context)
        return super(ShipmentInReturn, self).create(
            cursor, user, values, context=context)

    def set_state_draft(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.moves if m.state != 'draft'],
            {'state': 'draft'}, context=context)

    def set_state_waiting(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.moves if m.state not in ('cancel', 'draft')],
            {'state': 'draft', 'planned_date': shipment.planned_date,},
            context=context)

        self.write(
            cursor, user, shipment_id, {'state': 'waiting'}, context=context)

    def set_state_assigned(self, cursor, user, shipment_id, context=None):
        self.write(
            cursor, user, shipment_id, {'state': 'assigned'}, context=context)

    def set_state_done(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        date_obj = self.pool.get('ir.date')

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.moves if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'done',
            'effective_date': date_obj.today(cursor, user, context=context),
            }, context=context)

    def set_state_cancel(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.moves if m.state != 'cancel'],
            {'state': 'cancel'}, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'cancel'}, context=context)

    def assign_try(self, cursor, user, shipment_id, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        date_obj = self.pool.get('ir.date')
        move_obj = self.pool.get('stock.move')

        shipment = self.browse(cursor, user, shipment_id, context=context)

        cursor.execute('LOCK TABLE stock_move')

        local_ctx = context and context.copy() or {}
        local_ctx['stock_date_end'] = date_obj.today(cursor, user,
                context=context)
        local_ctx['stock_assign'] = True
        location_ids = [m.from_location.id for m in shipment.moves]
        pbl = product_obj.products_by_location(cursor, user,
            location_ids=location_ids,
            product_ids=[m.product.id for m in shipment.moves],
            context=local_ctx)

        for move in shipment.moves:
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
            else:
                return False

        move_obj.write(cursor, user, [m.id for m in shipment.moves],
                       {'state': 'assigned'}, context=context)
        return True

    def assign_force(self, cursor, user, shipment_id, context=None):
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(cursor, user, [m.id for m in shipment.moves], {
            'state': 'assigned',
            }, context=context)
        return True


ShipmentInReturn()


class ShipmentOut(ModelWorkflow, ModelSQL, ModelView):
    "Customer Shipment"
    _name = 'stock.shipment.out'
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
            }, domain=["('party', '=', customer)"])
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
    moves = fields.One2Many('stock.move', 'shipment_out', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('packed', 'Packed'),
        ('waiting', 'Waiting'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentOut, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE wkf "\
                "SET model = 'stock.shipment.out' "\
                "where model = 'stock.packing.out'")
        cursor.execute("UPDATE wkf_instance "\
                "SET res_type = 'stock.shipment.out' "\
                "where res_type = 'stock.packing.out'")
        cursor.execute("UPDATE wkf_trigger "\
                "SET model = 'stock.shipment.out' "\
                "WHERE model = 'stock.packing.out'")

        old_table = 'stock_packing_out'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, self._table)

        table = TableHandler(cursor, self, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        super(ShipmentOut, self).init(cursor, module_name)

        # Migration from 1.0 customer_location is no more used
        table = TableHandler(cursor, self, module_name)
        table.drop_column('customer_location', exception=True)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
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
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == \
                        shipment.warehouse.output_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_outgoing_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            shipment.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'outgoing_move_output_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            shipment.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'outgoing_move_output_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    shipment.warehouse.output_location.id:
                self.raise_user_error(cursor,
                        'outgoing_move_output_source', context=context)
        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == \
                        shipment.warehouse.output_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            shipment.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_output_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            shipment.warehouse.output_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_output_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    shipment.warehouse.output_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_output_dest', context=context)
        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def set_state_assigned(self, cursor, user, shipment_id, context=None):
        self.write(cursor, user, shipment_id, {'state': 'assigned'},
                   context=context)

    def set_state_draft(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.inventory_moves + shipment.outgoing_moves \
                 if m.state != 'draft'],
            {'state': 'draft'}, context=context)

    def set_state_done(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        date_obj = self.pool.get('ir.date')

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.outgoing_moves \
                               if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'done',
            'effective_date': date_obj.today(cursor, user, context=context),
            }, context=context)

    def set_state_packed(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.inventory_moves \
                               if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, shipment_id, {'state': 'packed'},
                   context=context)
        # Sum all outgoing quantities
        outgoing_qty = {}
        for move in shipment.outgoing_moves:
            if move.state == 'cancel': continue
            quantity = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                round=False, context=context)
            outgoing_qty.setdefault(move.product.id, 0.0)
            outgoing_qty[move.product.id] += quantity

        for move in shipment.inventory_moves:
            if move.state == 'cancel': continue
            qty_default_uom = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                round=False, context=context)
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
                    'to_location': shipment.customer.customer_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': out_quantity,
                    'shipment_out': shipment.id,
                    'state': 'draft',
                    'company': move.company.id,
                    'currency': move.company.currency.id,
                    'unit_price': unit_price,
                    }, context=context)

        #Re-read the shipment and remove exceeding quantities
        shipment = self.browse(cursor, user, shipment_id, context=context)
        for move in shipment.outgoing_moves:
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
                    move.product.default_uom, round=False, context=context)
                outgoing_qty[move.product.id] -= removed_qty

        move_obj.write(cursor, user, [x.id for x in shipment.outgoing_moves
            if x.state != 'cancel'], {
                'state': 'assigned',
                }, context=context)

    def set_state_cancel(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.outgoing_moves + shipment.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context=context)
        self.write(cursor, user, shipment_id, {'state': 'cancel'},
                   context=context)

    def set_state_waiting(self, cursor, user, shipment_id, context=None):
        """
        Complete inventory moves to match the products and quantities
        that are in the outgoing moves.
        """
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'waiting'}, context=context)

        if shipment.inventory_moves:
            move_obj.write(cursor, user,
                    [x.id for x in shipment.inventory_moves], {
                        'state': 'draft',
                        }, context=context)
            move_obj.delete(cursor, user,
                    [x.id for x in shipment.inventory_moves], context=context)

            # Re-Browse because moves have been deleted
            shipment = self.browse(cursor, user, shipment_id, context=context)

        for move in shipment.outgoing_moves:
            if move.state in ('cancel', 'done'):
                continue
            qty_default_uom = uom_obj.compute_qty(
                cursor, user, move.uom, move.quantity, move.product.default_uom,
                context=context)
            move_obj.create(cursor, user, {
                    'from_location': move.shipment_out.warehouse.storage_location.id,
                    'to_location': move.from_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': move.quantity,
                    'shipment_out': shipment.id,
                    'state': 'draft',
                    'company': move.company.id,
                    }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.shipment.out', context=context)
        return super(ShipmentOut, self).create(cursor, user, values,
                context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['outgoing_moves']= False
        return super(ShipmentOut, self).copy(cursor, user, ids,
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

    def assign_try(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        return move_obj.assign_try(
            cursor, user, shipment.inventory_moves, context=context)

    def assign_force(self, cursor, user, shipment_id, context=None):
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(
            cursor, user, [m.id for m in shipment.inventory_moves],
            {'state': 'assigned'})
        return True

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)

ShipmentOut()



class ShipmentOutReturn(ModelWorkflow, ModelSQL, ModelView):
    "Customer Return Shipment"
    _name = 'stock.shipment.out.return'
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
            }, domain=["('party', '=', customer)"])
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
    moves = fields.One2Many('stock.move', 'shipment_out_return', 'Moves',
            readonly=True)
    code = fields.Char("Code", size=None, select=1, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentOutReturn, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'incoming_move_input_dest': 'Incoming Moves must ' \
                    'have the warehouse input location as destination location!',
            'inventory_move_input_source': 'Inventory Moves must ' \
                    'have the warehouse input location as source location!',
            })

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE wkf "\
                "SET model = 'stock.shipment.out.return' "\
                "where model = 'stock.packing.out.return'")
        cursor.execute("UPDATE wkf_instance "\
                "SET res_type = 'stock.shipment.out.return' "\
                "where res_type = 'stock.packing.out.return'")
        cursor.execute("UPDATE wkf_trigger "\
                "SET model = 'stock.shipment.out.return' "\
                "WHERE model = 'stock.packing.out.return'")

        old_table = 'stock_packing_out_return'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, self._table)

        table = TableHandler(cursor, self, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        super(ShipmentOutReturn, self).init(cursor, module_name)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_warehouse(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.warehouse.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
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
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == \
                        shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_incoming_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    if act[1]['to_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    if act[2]['to_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'incoming_move_input_dest', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.to_location.id != \
                    shipment.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'incoming_move_input_dest', context=context)
        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def get_inventory_moves(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for shipment in self.browse(cursor, user, ids, context=context):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == \
                        shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, cursor, user, shipment_id, name, value, arg,
            context=None):
        move_obj = self.pool.get('stock.move')

        if not value:
            return

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    if act[1]['from_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    if act[2]['from_location'] != \
                            shipment.warehouse.input_location.id:
                        self.raise_user_error(cursor,
                                'inventory_move_input_source', context=context)
            elif act[0] == 'add':
                move_ids.append(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(cursor, user, move_ids, context=context)
        for move in moves:
            if move.from_location.id != \
                    shipment.warehouse.input_location.id:
                self.raise_user_error(cursor,
                        'inventory_move_input_source', context=context)
        self.write(cursor, user, shipment_id, {
            'moves': value,
            }, context=context)

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.shipment.out.return', context=context)
        return super(ShipmentOutReturn, self).create(cursor, user, values,
                context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(ShipmentOutReturn, self).copy(cursor, user, ids,
                default=default, context=context)


    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)

    def set_state_done(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        date_obj = self.pool.get('ir.date')

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.inventory_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context)
        self.write(cursor, user, shipment_id,{
            'state': 'done',
            'effective_date': date_obj.today(cursor, user, context=context),
            }, context=context)

    def set_state_cancel(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.incoming_moves + shipment.inventory_moves \
                 if m.state != 'cancel'],
            {'state': 'cancel'}, context)
        self.write(cursor, user, shipment_id, {'state': 'cancel'},
                   context=context)

    def set_state_received(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user,
            [m.id for m in shipment.incoming_moves \
                 if m.state not in ('done', 'cancel')],
            {'state': 'done'}, context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'received'
            }, context=context)

    def set_state_draft(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(cursor, user, [m.id for m in shipment.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            }, context=context)
        move_obj.delete(cursor, user,
                [m.id for m in shipment.inventory_moves], context=context)
        self.write(cursor, user, shipment_id, {
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
        res['to_location'] = incoming_move.shipment_out_return.warehouse.\
                storage_location.id
        res['state'] = 'draft'
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, cursor, user, shipment_id, context=None):
        shipment = self.browse(cursor, user, shipment_id, context=context)
        for incoming_move in shipment.incoming_moves:
            vals = self._get_inventory_moves(cursor, user, incoming_move,
                    context=context)
            if vals:
                self.write(cursor, user, shipment.id, {
                    'inventory_moves': [('create', vals)]
                    }, context=context)

ShipmentOutReturn()


class AssignShipmentOutAskForce(ModelView):
    'Assign Shipment Out Ask Force'
    _name = 'stock.shipment.out.assign.ask_force'
    _description = __doc__

    inventory_moves = fields.Many2Many('stock.move', None, None,
            'Inventory Moves', readonly=True)

AssignShipmentOutAskForce()


class AssignShipmentOut(Wizard):
    'Assign Shipment Out'
    _name = 'stock.shipment.out.assign'
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
                'object': 'stock.shipment.out.assign.ask_force',
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
        shipment_out_obj = self.pool.get('stock.shipment.out')

        shipment_out_obj.workflow_trigger_validate(cursor, user, data['id'],
                'assign', context=context)
        shipment = shipment_out_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in shipment.inventory_moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        shipment_out_obj = self.pool.get('stock.shipment.out')
        shipment = shipment_out_obj.browse(cursor, user, data['id'],
                context=context)
        return {'inventory_moves': [x.id for x in shipment.inventory_moves
            if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        shipment_out_obj = self.pool.get('stock.shipment.out')

        shipment_out_obj.workflow_trigger_validate(cursor, user, data['id'],
                'force_assign', context=context)
        return {}

AssignShipmentOut()


class ShipmentInternal(ModelWorkflow, ModelSQL, ModelView):
    "Internal Shipment"
    _name = 'stock.shipment.internal'
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
        domain=["('type', 'not in', " \
                    "('supplier', 'customer', 'warehouse', 'view'))"])
    to_location = fields.Many2One('stock.location', "To Location",
            required=True, states={
                'readonly': "state != 'draft' or bool(moves)",
            }, domain=["('type', 'not in', " \
                    "('supplier', 'customer', 'warehouse', 'view'))"])
    moves = fields.One2Many(
        'stock.move', 'shipment_internal', 'Moves',
        states={'readonly': "state != 'draft' or "\
                    "not(bool(from_location) and bool (to_location))"},
        context="{'from_location': from_location,"
                "'to_location': to_location,"
                "'planned_date': planned_date}",
        )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def init(self, cursor, module_name):
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE wkf "\
                "SET model = 'stock.shipment.internal' "\
                "where model = 'stock.packing.internal'")
        cursor.execute("UPDATE wkf_instance "\
                "SET res_type = 'stock.shipment.internal' "\
                "where res_type = 'stock.packing.internal'")
        cursor.execute("UPDATE wkf_trigger "\
                "SET model = 'stock.shipment.internal' "\
                "WHERE model = 'stock.packing.internal'")

        old_table = 'stock_packing_internal'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, self._table)
        table = TableHandler(cursor, self, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        super(ShipmentInternal, self).init(cursor, module_name)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def button_draft(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        return True

    def __init__(self):
        super(ShipmentInternal, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
            cursor, user, 'stock.shipment.internal', context=context)
        return super(ShipmentInternal, self).create(
            cursor, user, values, context=context)

    def set_state_draft(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'draft'}, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.moves], {'state': 'draft'},
            context=context)

    def set_state_waiting(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(cursor, user, [m.id for m in shipment.moves], {
            'from_location': shipment.from_location.id,
            'to_location': shipment.to_location.id,
            'state': 'draft',
            'planned_date': shipment.planned_date,
            }, context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'waiting'}, context=context)

    def set_state_assigned(self, cursor, user, shipment_id, context=None):
        self.write(
            cursor, user, shipment_id, {'state': 'assigned'}, context=context)

    def set_state_done(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        date_obj = self.pool.get('ir.date')

        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.moves], {'state': 'done'},
            context=context)
        self.write(cursor, user, shipment_id, {
            'state': 'done',
            'effective_date': date_obj.today(cursor, user, context=context),
            }, context=context)

    def set_state_cancel(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj.write(
            cursor, user, [m.id for m in shipment.moves], {'state': 'cancel'},
            context=context)
        self.write(
            cursor, user, shipment_id, {'state': 'cancel'}, context=context)

    def assign_try(self, cursor, user, shipment_id, context=None):
        move_obj = self.pool.get('stock.move')
        shipment = self.browse(cursor, user, shipment_id, context=context)
        return move_obj.assign_try(
            cursor, user, shipment.moves, context=context)

    def assign_force(self, cursor, user, shipment_id, context=None):
        shipment = self.browse(cursor, user, shipment_id, context=context)
        move_obj = self.pool.get('stock.move')
        move_obj.write(cursor, user, [m.id for m in shipment.moves], {
            'state': 'assigned',
            }, context=context)
        return True

ShipmentInternal()


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    delivery = fields.Boolean('Delivery')

Address()


class AssignShipmentInternalAskForce(ModelView):
    'Assign Shipment Internal Ask Force'
    _name = 'stock.shipment.internal.assign.ask_force'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

AssignShipmentInternalAskForce()


class AssignShipmentInternal(Wizard):
    'Assign Shipment Internal'
    _name = 'stock.shipment.internal.assign'
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
                'object': 'stock.shipment.internal.assign.ask_force',
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
        shipment_internal_obj = self.pool.get('stock.shipment.internal')

        shipment_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'assign', context=context)
        shipment = shipment_internal_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in shipment.moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        shipment_internal_obj = self.pool.get('stock.shipment.internal')
        shipment = shipment_internal_obj.browse(cursor, user, data['id'],
                context=context)
        return {'moves': [x.id for x in shipment.moves if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        shipment_internal_obj = self.pool.get('stock.shipment.internal')

        shipment_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'force_assign', context=context)
        return {}

AssignShipmentInternal()


class AssignShipmentInReturnAskForce(ModelView):
    'Assign Supplier Return Shipment Ask Force'
    _name = 'stock.shipment.in.return.assign.ask_force'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

AssignShipmentInReturnAskForce()


class AssignShipmentInReturn(Wizard):
    'Assign Supplier Return Shipment'
    _name = 'stock.shipment.in.return.assign'
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
                'object': 'stock.shipment.in.return.assign.ask_force',
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
        shipment_internal_obj = self.pool.get('stock.shipment.in.return')

        shipment_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'assign', context=context)
        shipment = shipment_internal_obj.browse(cursor, user, data['id'],
                context=context)
        if not [x.id for x in shipment.moves if x.state == 'draft']:
            return 'end'
        else:
            return 'ask_force'

    def _moves(self, cursor, user, data, context=None):
        shipment_internal_obj = self.pool.get('stock.shipment.in.return')
        shipment = shipment_internal_obj.browse(cursor, user, data['id'],
                context=context)
        return {'moves': [x.id for x in shipment.moves if x.state == 'draft']}

    def _force(self, cursor, user, data, context=None):
        shipment_internal_obj = self.pool.get('stock.shipment.in.return')

        shipment_internal_obj.workflow_trigger_validate(cursor, user,
                data['id'], 'force_assign', context=context)
        return {}

AssignShipmentInReturn()


class CreateShipmentOutReturn(Wizard):
    'Create Customer Return Shipment'
    _name = 'stock.shipment.out.return.create'
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
        super(CreateShipmentOutReturn, self).__init__()
        self._error_messages.update({
            'shipment_done_title': 'You can not create return shipment',
            'shipment_done_msg': 'The shipment with code %s is not yet sent.',
            })


    def _create(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        shipment_out_obj = self.pool.get('stock.shipment.out')
        shipment_out_return_obj = self.pool.get('stock.shipment.out.return')

        shipment_outs = shipment_out_obj.browse(
            cursor, user, data['ids'], context=context)

        shipment_out_return_ids = []
        for shipment_out in shipment_outs:
            if shipment_out.state != 'done':
                self.raise_user_error(
                    cursor, 'shipment_done_title',
                    error_description='shipment_done_msg',
                    error_description_args=shipment_out.code,
                    context=context)

            incoming_moves = []
            for move in shipment_out.outgoing_moves:
                incoming_moves.append(('create', {
                            'product': move.product.id,
                            'quantity': move.quantity,
                            'uom': move.uom.id,
                            'from_location': move.to_location.id,
                            'to_location': shipment_out.warehouse.input_location.id,
                            'company': move.company.id,
                            }))
            shipment_out_return_ids.append(
                shipment_out_return_obj.create(
                    cursor, user,
                    {'customer': shipment_out.customer.id,
                     'delivery_address': shipment_out.delivery_address.id,
                     'warehouse': shipment_out.warehouse.id,
                     'incoming_moves': incoming_moves,
                     },
                    context=context)
                )

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_shipment_out_return_form'),
            ('module', '=', 'stock'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['res_id'] = shipment_out_return_ids
        if len(shipment_out_return_ids) == 1:
            res['views'].reverse()

        return res

CreateShipmentOutReturn()


class DeliveryNote(CompanyReport):
    _name = 'stock.shipment.out.delivery_note'

    def parse(self, cursor, user, report, objects, datas, context):
        if context is None:
            context = {}
        context = context.copy()
        context['product_name'] = lambda product_id, language: \
                self.product_name(cursor, user, product_id, language,
                        context)
        return super(DeliveryNote, self).parse(cursor, user, report,
                objects, datas, context)

    def product_name(self, cursor, user, product_id, language, context):
        product_obj = self.pool.get('product.product')
        ctx = context.copy()
        ctx['language'] = language
        return product_obj.browse(cursor, user, product_id,
                context=ctx).rec_name

DeliveryNote()


class PickingList(CompanyReport):
    _name = 'stock.shipment.out.picking_list'

    def parse(self, cursor, user, report, objects, datas, context):
        move_obj = self.pool.get('stock.move')
        shipment_out_obj = self.pool.get('stock.shipment.out')

        compare_context = self.get_compare_context(
            cursor, user, report, objects, datas, context)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        context['moves'] = sorted_moves

        return super(PickingList, self).parse(cursor, user, report,
                objects, datas, context)

    def get_compare_context(self, cursor, user, report, objects, datas, context):
        location_obj = self.pool.get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(
            cursor, user, list(from_location_ids), context=context)
        to_location_ids = location_obj.search(
            cursor, user, list(to_location_ids), context=context)

        return {'from_location_ids' : from_location_ids,
                'to_location_ids' : to_location_ids}


    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

PickingList()


class SupplierRestockingList(CompanyReport):
    _name = 'stock.shipment.in.restocking_list'

    def parse(self, cursor, user, report, objects, datas, context):
        move_obj = self.pool.get('stock.move')
        shipment_in_obj = self.pool.get('stock.shipment.in')

        compare_context = self.get_compare_context(
            cursor, user, report, objects, datas, context)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        context['moves'] = sorted_moves

        return super(SupplierRestockingList, self).parse(cursor, user, report,
                objects, datas, context)

    def get_compare_context(self, cursor, user, report, objects, datas, context):
        location_obj = self.pool.get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(
            cursor, user, list(from_location_ids), context=context)
        to_location_ids = location_obj.search(
            cursor, user, list(to_location_ids), context=context)

        return {'from_location_ids' : from_location_ids,
                'to_location_ids' : to_location_ids}


    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

SupplierRestockingList()


class CustomerReturnRestockingList(CompanyReport):
    _name = 'stock.shipment.out.return.restocking_list'

    def parse(self, cursor, user, report, objects, datas, context):
        move_obj = self.pool.get('stock.move')
        shipment_in_obj = self.pool.get('stock.shipment.out.return')

        compare_context = self.get_compare_context(
            cursor, user, report, objects, datas, context)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        context['moves'] = sorted_moves

        return super(CustomerReturnRestockingList, self).parse(
            cursor, user, report, objects, datas, context)

    def get_compare_context(self, cursor, user, report, objects, datas, context):
        location_obj = self.pool.get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(
            cursor, user, list(from_location_ids), context=context)
        to_location_ids = location_obj.search(
            cursor, user, list(to_location_ids), context=context)

        return {'from_location_ids' : from_location_ids,
                'to_location_ids' : to_location_ids}


    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

CustomerReturnRestockingList()


class InteralShipmentReport(CompanyReport):
    _name = 'stock.shipment.internal.report'

    def parse(self, cursor, user, report, objects, datas, context):
        move_obj = self.pool.get('stock.move')
        shipment_in_obj = self.pool.get('stock.shipment.internal')

        compare_context = self.get_compare_context(
            cursor, user, report, objects, datas, context)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        context['moves'] = sorted_moves

        return super(InteralShipmentReport, self).parse(
            cursor, user, report, objects, datas, context)

    def get_compare_context(self, cursor, user, report, objects, datas, context):
        location_obj = self.pool.get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(
            cursor, user, list(from_location_ids), context=context)
        to_location_ids = location_obj.search(
            cursor, user, list(to_location_ids), context=context)

        return {'from_location_ids' : from_location_ids,
                'to_location_ids' : to_location_ids}


    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

InteralShipmentReport()
