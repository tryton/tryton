#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import operator
import itertools
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Eval, Not, Equal, If, Or, And, Bool, In, Get
from trytond.transaction import Transaction
from trytond.pool import Pool

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class ShipmentIn(ModelWorkflow, ModelSQL, ModelView):
    "Supplier Shipment"
    _name = 'stock.shipment.in'
    _description = __doc__
    _rec_name = 'code'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    reference = fields.Char("Reference", size=None, select=1,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    supplier = fields.Many2One('party.party', 'Supplier',
        states={
            'readonly': And(Or(Not(Equal(Eval('state'), 'draft')),
                    Bool(Eval('incoming_moves'))), Bool(Eval('supplier'))),
            }, on_change=['supplier'], required=True,
        depends=['state', 'incoming_moves', 'supplier'])
    contact_address = fields.Many2One('party.address', 'Contact Address',
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[('party', '=', Eval('supplier'))],
        depends=['state', 'supplier'])
    warehouse = fields.Many2One('stock.location', "Warehouse",
        required=True, domain=[('type', '=', 'warehouse')],
        states={
            'readonly': Or(In(Eval('state'), ['cancel', 'done']),
                Bool(Eval('incoming_moves'))),
            }, depends=['state', 'incoming_moves'])
    incoming_moves = fields.Function(fields.One2Many('stock.move', None,
        'Incoming Moves', add_remove=[
            ('shipment_in', '=', False),
            ('from_location.type', '=', 'supplier'),
            ('state', '=', 'draft'),
            ('to_location_warehouse', '=', Eval('warehouse')),
        ],
        states={
            'readonly': Or(In(Eval('state'), ['received', 'done', 'cancel']),
                Not(Bool(Eval('warehouse')))),
        }, context={
            'warehouse': Eval('warehouse'),
            'type': 'incoming',
            'supplier': Eval('supplier'),
        }, depends=['state', 'warehouse']),
        'get_incoming_moves', setter='set_incoming_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
        'Inventory Moves', states={
            'readonly': In(Eval('state'), ['draft', 'done', 'cancel']),
        }, context={
            'warehouse': Eval('warehouse'),
            'type': 'inventory_in',
        }, depends=['state', 'warehouse']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_in', 'Moves',
        domain=[('company', '=', Eval('company'))], readonly=True,
        depends=['company'])
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

    def init(self, module_name):
        cursor = Transaction().cursor
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

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentIn, self).init(module_name)

        # Migration from 2.0:
        move_obj = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, move_obj._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move ON shipment.id = move.shipment_in '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (self._table, move_obj._table))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                self.write(shipment_ids, {'company': company_id})
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_warehouse(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def on_change_supplier(self, values):
        if not values.get('supplier'):
            return {'contact_address': False}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['supplier'])
        return {'contact_address': address_id}

    def get_incoming_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_incoming_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['to_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('incoming_move_input_dest')
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['to_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('incoming_move_input_dest')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.to_location.id != \
                        shipment.warehouse.input_location.id:
                    self.raise_user_error('incoming_move_input_dest')

        self.write(ids, {
            'moves': value,
            })

    def get_inventory_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['from_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('inventory_move_input_source')
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['from_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('inventory_move_input_source')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.from_location.id != \
                        shipment.warehouse.input_location.id:
                    self.raise_user_error('inventory_move_input_source')

        self.write(ids, {
            'moves': value,
            })

    def wkf_done(self, shipment):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        move_obj.write([m.id for m in shipment.inventory_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id,{
            'state': 'done',
            'effective_date': date_obj.today(),
            })

    def wkf_cancel(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.incoming_moves
            if m.state != 'cancel'] +
            [m.id for m in shipment.inventory_moves
                if m.state != 'cancel'], {
                    'state': 'cancel',
                    })
        self.write(shipment.id, {
            'state': 'cancel',
            })

    def wkf_received(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.incoming_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
            })
        self.write(shipment.id, {
            'state': 'received'
            })
        self.create_inventory_moves(shipment.id)

    def wkf_draft(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            })
        move_obj.delete([m.id for m in shipment.inventory_moves])
        self.write(shipment.id, {
            'state': 'draft',
            })

    def _get_move_planned_date(self, shipment):
        '''
        Return the planned date for incoming moves and inventory_moves
        '''
        return shipment.planned_date, shipment.planned_date

    def _set_move_planned_date(self, shipment_ids):
        '''
        Set planned date of moves for the shipments
        '''
        move_obj = Pool().get('stock.move')
        if isinstance(shipment_ids, (int, long)):
            shipment_ids = [shipment_ids]
        for shipment in self.browse(shipment_ids):
            dates = self._get_move_planned_date(shipment)
            incoming_date, inventory_date = dates
            move_obj.write([x.id for x in shipment.incoming_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': incoming_date,
                    })
            move_obj.write([x.id for x in shipment.inventory_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': inventory_date,
                    })

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(config.shipment_in_sequence.id)
        shipment_id = super(ShipmentIn, self).create(values)
        self._set_move_planned_date(shipment_id)
        return shipment_id

    def write(self, ids, values):
        result = super(ShipmentIn, self).write(ids, values)
        self._set_move_planned_date(ids)
        return result

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(ShipmentIn, self).copy(ids, default=default)

    def _get_inventory_moves(self, incoming_move):
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
        # Product will be considered in stock only when the inventory
        # move will be made:
        res['planned_date'] = False
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, shipment_id):
        shipment = self.browse(shipment_id)
        for incoming_move in shipment.incoming_moves:
            vals = self._get_inventory_moves(incoming_move)
            if vals:
                self.write(shipment.id, {
                    'inventory_moves': [('create', vals)],
                    })

    def button_draft(self, ids):
        self.workflow_trigger_create(ids)
        return True

ShipmentIn()


class ShipmentInReturn(ModelWorkflow, ModelSQL, ModelView):
    "Supplier Return Shipment"
    _name = 'stock.shipment.in.return'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    code = fields.Char("Code", size=None, select=1, readonly=True)
    reference = fields.Char("Reference", size=None, select=1,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    from_location = fields.Many2One('stock.location', "From Location",
        required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('moves'))),
            }, domain=[('type', '=', 'storage')],
        depends=['state', 'moves'])
    to_location = fields.Many2One('stock.location', "To Location",
        required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('moves'))),
            }, domain=[('type', '=', 'supplier')],
        depends=['state', 'moves'])
    moves = fields.One2Many('stock.move', 'shipment_in_return', 'Moves',
        states={
            'readonly': And(Or(Not(Equal(Eval('state'), 'draft')),
                    Not(Bool(Eval('from_location')))),
                Bool(Eval('to_location'))),
            },
        domain=[('company', '=', Eval('company'))],
        context={
            'from_location': Eval('from_location'),
            'to_location': Eval('to_location'),
            'planned_date': Eval('planned_date'),
            },
        depends=['state', 'from_location', 'to_location', 'company'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def default_state(self):
        return 'draft'

    def button_draft(self, ids):
        self.workflow_trigger_create(ids)
        return True

    def init(self, module_name):
        cursor = Transaction().cursor
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

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentInReturn, self).init(module_name)

        # Migration from 2.0:
        move_obj = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, move_obj._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON shipment.id = move.shipment_in_return '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (self._table, move_obj._table))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                self.write(shipment_ids, {'company': company_id})
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def __init__(self):
        super(ShipmentInReturn, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')

    def _get_move_planned_date(self, shipment):
        '''
        Return the planned date for the moves
        '''
        return shipment.planned_date

    def _set_move_planned_date(self, shipment_ids):
        '''
        Set planned date of moves for the shipments
        '''
        move_obj = Pool().get('stock.move')
        if isinstance(shipment_ids, (int, long)):
            shipment_ids = [shipment_ids]
        for shipment in self.browse(shipment_ids):
            date = self._get_move_planned_date(shipment)
            move_obj.write([x.id for x in shipment.moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': date,
                    })

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(
                config.shipment_in_return_sequence.id)
        shipment_id = super(ShipmentInReturn, self).create(values)
        self._set_move_planned_date(shipment_id)
        return shipment_id

    def write(self, ids, values):
        result = super(ShipmentInReturn, self).write(ids, values)
        self._set_move_planned_date(ids)
        return result

    def default_company(self):
        return Transaction().context.get('company') or False

    def wkf_draft(self, shipment):
        move_obj = Pool().get('stock.move')
        self.write(shipment.id, {
            'state': 'draft',
            })
        move_obj.write([m.id for m in shipment.moves if m.state != 'draft'], {
            'state': 'draft',
            })

    def wkf_waiting(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves
            if m.state not in ('cancel', 'draft')], {
                'state': 'draft',
                'planned_date': shipment.planned_date,
                })

        self.write(shipment.id, {
            'state': 'waiting',
            })

    def wkf_assigned(self, shipment):
        self.write(shipment.id, {
            'state': 'assigned',
            })

    def wkf_done(self, shipment):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        move_obj.write([m.id for m in shipment.moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id, {
            'state': 'done',
            'effective_date': date_obj.today(),
            })

    def wkf_cancel(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves if m.state != 'cancel'], {
            'state': 'cancel',
            })
        self.write(shipment.id, {
            'state': 'cancel',
            })

    def wkf_assign_try(self, shipment):
        pool = Pool()
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')
        date_obj = pool.get('ir.date')
        move_obj = pool.get('stock.move')

        Transaction().cursor.lock(move_obj._table)

        location_ids = [m.from_location.id for m in shipment.moves]
        with Transaction().set_context(
                stock_date_end=date_obj.today(),
                stock_assign=True):
            pbl = product_obj.products_by_location(location_ids=location_ids,
                    product_ids=[m.product.id for m in shipment.moves])

        for move in shipment.moves:
            if move.state != 'draft':
                continue
            if (move.from_location.id, move.product.id) in pbl:
                qty_default_uom = pbl[(move.from_location.id, move.product.id)]
                qty = uom_obj.compute_qty(move.product.default_uom,
                        qty_default_uom, move.uom, round=False)
                if qty < move.quantity:
                    return False
                pbl[(move.from_location.id, move.product.id)] = \
                    pbl[(move.from_location.id, move.product.id)] - qty_default_uom
            else:
                return False

        move_obj.write([m.id for m in shipment.moves], {
            'state': 'assigned',
            })
        return True

    def wkf_assign_force(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves], {
            'state': 'assigned',
            })
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
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('outgoing_moves'))),
            }, on_change=['customer'],
        depends=['state', 'outgoing_moves'])
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=1,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('outgoing_moves'))),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state', 'outgoing_moves'])
    outgoing_moves = fields.Function(fields.One2Many('stock.move', None,
            'Outgoing Moves', states={
                'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                    Not(Bool(Eval('warehouse')))),
                }, context={
                'warehouse': Eval('warehouse'),
                'type': 'outgoing',
                'customer': Eval('customer'),
                }, depends=['state', 'warehouse', 'customer']),
        'get_outgoing_moves', setter='set_outgoing_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
            'Inventory Moves', states={
                'readonly': In(Eval('state'), ['draft', 'packed', 'done']),
                }, context={
                'warehouse': Eval('warehouse'),
                'type': 'inventory_out',
                }, depends=['state', 'warehouse']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_out', 'Moves',
        domain=[('company', '=', Eval('company'))], depends=['company'],
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
        self._error_messages.update({
            'outgoing_move_output_source': 'Outgoing Moves must ' \
                    'have the warehouse output location as source location!',
            'inventory_move_output_dest': 'Inventory Moves must have the ' \
                    'warehouse output location as destination location!',
            })

    def init(self, module_name):
        cursor = Transaction().cursor
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

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentOut, self).init(module_name)

        # Migration from 2.0:
        move_obj = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, move_obj._table)):
            move_obj = Pool().get('stock.move')
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move ON shipment.id = move.shipment_out '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (self._table, move_obj._table))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                self.write(shipment_ids, {'company': company_id})
            table.not_null_action('company', action='add')

        # Migration from 1.0 customer_location is no more used
        table = TableHandler(cursor, self, module_name)
        table.drop_column('customer_location', exception=True)

        # Add index on create_date
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_warehouse(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def on_change_customer(self, values):
        if not values.get('customer'):
            return {'delivery_address': False}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['customer'], type='delivery')
        return {'delivery_address': address_id}

    def get_outgoing_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == \
                        shipment.warehouse.output_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_outgoing_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['from_location'] != \
                                shipment.warehouse.output_location.id:
                            self.raise_user_error(
                                    'outgoing_move_output_source')
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['from_location'] != \
                                shipment.warehouse.output_location.id:
                            self.raise_user_error(
                                    'outgoing_move_output_source')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.from_location.id != \
                        shipment.warehouse.output_location.id:
                    self.raise_user_error('outgoing_move_output_source')
        self.write(ids, {
            'moves': value,
            })

    def get_inventory_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == \
                        shipment.warehouse.output_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['to_location'] != \
                                shipment.warehouse.output_location.id:
                            self.raise_user_error(
                                    'inventory_move_output_dest')
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['to_location'] != \
                                shipment.warehouse.output_location.id:
                            self.raise_user_error(
                                    'inventory_move_output_dest')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.to_location.id != \
                        shipment.warehouse.output_location.id:
                    self.raise_user_error('inventory_move_output_dest')
        self.write(ids, {
            'moves': value,
            })

    def wkf_assigned(self, shipment):
        self.write(shipment.id, {
            'state': 'assigned',
            })

    def wkf_draft(self, shipment):
        move_obj = Pool().get('stock.move')
        self.write(shipment.id, {
            'state': 'draft',
            })
        move_obj.write([m.id for m in
            shipment.inventory_moves + shipment.outgoing_moves
            if m.state != 'draft'], {
                'state': 'draft',
                })

    def wkf_done(self, shipment):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        move_obj.write([m.id for m in shipment.outgoing_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id, {
            'state': 'done',
            'effective_date': date_obj.today(),
            })

    def wkf_packed(self, shipment):
        move_obj = Pool().get('stock.move')
        uom_obj = Pool().get('product.uom')
        move_obj.write([m.id for m in shipment.inventory_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id, {
            'state': 'packed',
            })
        # Sum all outgoing quantities
        outgoing_qty = {}
        for move in shipment.outgoing_moves:
            if move.state == 'cancel': continue
            quantity = uom_obj.compute_qty(move.uom, move.quantity,
                    move.product.default_uom, round=False)
            outgoing_qty.setdefault(move.product.id, 0.0)
            outgoing_qty[move.product.id] += quantity

        for move in shipment.inventory_moves:
            if move.state == 'cancel': continue
            qty_default_uom = uom_obj.compute_qty(move.uom, move.quantity,
                    move.product.default_uom, round=False)
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
                            move.product.default_uom, out_quantity, move.uom)
                    outgoing_qty[move.product.id] = 0.0
            else:
                out_quantity = move.quantity

            unit_price = uom_obj.compute_price(move.product.default_uom,
                    move.product.list_price, move.uom)
            move_obj.create({
                    'from_location': move.to_location.id,
                    'to_location': shipment.customer.customer_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': out_quantity,
                    'shipment_out': shipment.id,
                    'state': 'draft',
                    'planned_date': shipment.planned_date,
                    'company': move.company.id,
                    'currency': move.company.currency.id,
                    'unit_price': unit_price,
                    })

        #Re-read the shipment and remove exceeding quantities
        for move in shipment.outgoing_moves:
            if move.state == 'cancel': continue
            if outgoing_qty.get(move.product.id, 0.0) > 0.0:
                exc_qty = uom_obj.compute_qty(move.product.default_uom,
                        outgoing_qty[move.product.id], move.uom)
                move_obj.write(move.id,{
                    'quantity': max(0.0, move.quantity-exc_qty),
                    })
                removed_qty = uom_obj.compute_qty(move.uom,
                        min(exc_qty, move.quantity), move.product.default_uom,
                        round=False)
                outgoing_qty[move.product.id] -= removed_qty

        move_obj.write([x.id for x in shipment.outgoing_moves
            if x.state != 'cancel'], {
                'state': 'assigned',
                })

    def wkf_cancel(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in
            shipment.outgoing_moves + shipment.inventory_moves
            if m.state != 'cancel'], {
                'state': 'cancel',
                })
        self.write(shipment.id, {
            'state': 'cancel',
            })

    def wkf_waiting(self, shipment):
        """
        Complete inventory moves to match the products and quantities
        that are in the outgoing moves.
        """
        move_obj = Pool().get('stock.move')
        self.write(shipment.id, {
            'state': 'waiting',
            })

        if shipment.inventory_moves:
            move_obj.write( [x.id for x in shipment.inventory_moves], {
                'state': 'draft',
                })
            move_obj.delete([x.id for x in shipment.inventory_moves])

            # Re-Browse because moves have been deleted
            shipment = self.browse(shipment.id)

        for move in shipment.outgoing_moves:
            if move.state in ('cancel', 'done'):
                continue
            move_obj.create({
                    'from_location': \
                        move.shipment_out.warehouse.storage_location.id,
                    'to_location': move.from_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': move.quantity,
                    'shipment_out': shipment.id,
                    'planned_date': move.planned_date,
                    'state': 'draft',
                    'company': move.company.id,
                    'currency': move.currency.id,
                    'unit_price': move.unit_price,
                    })

    def _get_move_planned_date(self, shipment):
        '''
        Return the planned date for outgoing moves and inventory moves
        '''
        return shipment.planned_date, shipment.planned_date

    def _set_move_planned_date(self, shipment_ids):
        '''
        Set planned date of moves for the shipments
        '''
        move_obj = Pool().get('stock.move')
        if isinstance(shipment_ids, (int, long)):
            shipment_ids = [shipment_ids]
        for shipment in self.browse(shipment_ids):
            dates = self._get_move_planned_date(shipment)
            outgoing_date, inventory_date = dates
            move_obj.write([x.id for x in shipment.outgoing_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': outgoing_date,
                    })
            move_obj.write([x.id for x in shipment.inventory_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': inventory_date,
                    })

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(config.shipment_out_sequence.id)
        shipment_id = super(ShipmentOut, self).create(values)
        self._set_move_planned_date(shipment_id)
        return shipment_id

    def write(self, ids, values):
        result = super(ShipmentOut, self).write(ids, values)
        self._set_move_planned_date(ids)
        return result

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['outgoing_moves']= False
        return super(ShipmentOut, self).copy(ids, default=default)


    def _location_amount(self, target_uom, qty_uom, uom_index):
        """
        Take a raw list of quantities and uom and convert it to
        the target uom.
        """
        uom_obj = Pool().get('product.uom')
        res = 0
        for uom, qty in qty_uom:
            res += uom_obj.compute_qty(uom_index[uom], qty,
                    uom_index[target_uom])
        return res

    def wkf_assign_try(self, shipment):
        move_obj = Pool().get('stock.move')
        return move_obj.assign_try(shipment.inventory_moves)

    def wkf_assign_force(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.inventory_moves], {
            'state': 'assigned',
            })
        return True

    def button_draft(self, ids):
        self.workflow_trigger_create(ids)

ShipmentOut()



class ShipmentOutReturn(ModelWorkflow, ModelSQL, ModelView):
    "Customer Return Shipment"
    _name = 'stock.shipment.out.return'
    _description = __doc__
    _rec_name = 'code'

    effective_date = fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('incoming_moves'))),
            }, on_change=['customer'],
        depends=['state', 'incoming_moves'])
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=1,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('incoming_moves'))),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state', 'incoming_moves'])
    incoming_moves = fields.Function(fields.One2Many('stock.move', None,
            'Incoming Moves', states={
                'readonly': Not(Equal(Eval('state'), 'draft')),
                }, context={
                'warehouse': Eval('warehouse'),
                'type': 'incoming',
                'customer': Eval('customer'),
                }, depends=['state', 'warehouse', 'customer']),
        'get_incoming_moves', setter='set_incoming_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
            'Inventory Moves', states={
                'readonly': In(Eval('state'), ['draft', 'cancel', 'done']),
                }, context={
                'warehouse': Eval('warehouse'),
                'type': 'inventory_out',
                }, depends=['state', 'warehouse']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_out_return', 'Moves',
        domain=[('company', '=', Eval('company'))], depends=['company'],
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

    def init(self, module_name):
        cursor = Transaction().cursor
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

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentOutReturn, self).init(module_name)

        # Migration from 2.0:
        move_obj = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, move_obj._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON shipment.id = move.shipment_out_return '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (self._table, move_obj._table))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                self.write(shipment_ids, {'company': company_id})
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_warehouse(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.warehouse.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def on_change_customer(self, values):
        if not values.get('customer'):
            return {'delivery_address': False}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['customer'], type='delivery')
        return {
                'delivery_address': address_id,
            }

    def get_incoming_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == \
                        shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_incoming_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'to_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['to_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('incoming_move_input_dest')
            elif act[0] == 'write':
                if 'to_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['to_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error('incoming_move_input_dest')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.to_location.id != \
                        shipment.warehouse.input_location.id:
                    self.raise_user_error('incoming_move_input_dest')

        self.write(ids, {
            'moves': value,
            })

    def get_inventory_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.from_location.id == \
                        shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, ids, name, value):
        move_obj = Pool().get('stock.move')

        if not value:
            return

        shipments = self.browse(ids)
        move_ids = []
        for act in value:
            if act[0] == 'create':
                if 'from_location' in act[1]:
                    for shipment in shipments:
                        if act[1]['from_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error(
                                    'inventory_move_input_source')
            elif act[0] == 'write':
                if 'from_location' in act[2]:
                    for shipment in shipments:
                        if act[2]['from_location'] != \
                                shipment.warehouse.input_location.id:
                            self.raise_user_error(
                                    'inventory_move_input_source')
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    move_ids.append(act[1])
                else:
                    move_ids.extend(act[1])
            elif act[0] == 'set':
                move_ids.extend(act[1])

        moves = move_obj.browse(move_ids)
        for move in moves:
            for shipment in shipments:
                if move.from_location.id != \
                        shipment.warehouse.input_location.id:
                    self.raise_user_error('inventory_move_input_source')

        self.write(ids, {
            'moves': value,
            })

    def _get_move_planned_date(self, shipment):
        '''
        Return the planned date for incoming moves and inventory moves
        '''
        return shipment.planned_date, shipment.planned_date

    def _set_move_planned_date(self, shipment_ids):
        '''
        Set planned date of moves for the shipments
        '''
        move_obj = Pool().get('stock.move')
        if isinstance(shipment_ids, (int, long)):
            shipment_ids = [shipment_ids]
        for shipment in self.browse(shipment_ids):
            dates = self._get_move_planned_date(shipment)
            incoming_date, inventory_date = dates
            move_obj.write([x.id for x in shipment.incoming_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
                    'planned_date': incoming_date,
                    })
            move_obj.write([x.id for x in shipment.inventory_moves], {
                    'planned_date': inventory_date,
                    })

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(
                config.shipment_out_return_sequence.id)
        shipment_id = super(ShipmentOutReturn, self).create(values)
        self._set_move_planned_date(shipment_id)
        return shipment_id

    def write(self, ids, values):
        result = super(ShipmentOutReturn, self).write(ids, values)
        self._set_move_planned_date(ids)
        return result

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves']= False
        default['incoming_moves']= False
        return super(ShipmentOutReturn, self).copy(ids, default=default)


    def button_draft(self, ids):
        self.workflow_trigger_create(ids)

    def wkf_done(self, shipment):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        move_obj.write([m.id for m in shipment.inventory_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id,{
            'state': 'done',
            'effective_date': date_obj.today(),
            })

    def wkf_cancel(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in
            shipment.incoming_moves + shipment.inventory_moves
            if m.state != 'cancel'], {
                'state': 'cancel',
                })
        self.write(shipment.id, {
            'state': 'cancel',
            })

    def wkf_received(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.incoming_moves
            if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(shipment.id, {
            'state': 'received'
            })
        self.create_inventory_moves(shipment.id)

    def wkf_draft(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.incoming_moves
            if m.state != 'draft'], {
            'state': 'draft',
            })
        move_obj.delete([m.id for m in shipment.inventory_moves])
        self.write(shipment.id, {
            'state': 'draft',
            })

    def _get_inventory_moves(self, incoming_move):
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
        # Product will be considered in stock only when the inventory
        # move will be made:
        res['planned_date'] = False
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, shipment_id):
        shipment = self.browse(shipment_id)
        for incoming_move in shipment.incoming_moves:
            vals = self._get_inventory_moves(incoming_move)
            if vals:
                self.write(shipment.id, {
                    'inventory_moves': [('create', vals)],
                    })

ShipmentOutReturn()


class AssignShipmentOutAssignFailed(ModelView):
    'Assign Shipment Out Assign Failed'
    _name = 'stock.shipment.out.assign.assign_failed'
    _description = __doc__

    inventory_moves = fields.Many2Many('stock.move', None, None,
            'Inventory Moves', readonly=True)

AssignShipmentOutAssignFailed()


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
        'assign_failed': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.out.assign.assign_failed',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.out.assign.assign_failed',
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

    def _choice(self, data):
        pool = Pool()
        shipment_out_obj = pool.get('stock.shipment.out')
        user_group_obj = pool.get('res.user-res.group')
        model_data_obj = pool.get('ir.model.data')
        transition_obj = pool.get('workflow.transition')

        shipment_out_obj.workflow_trigger_validate(data['id'], 'assign')
        shipment = shipment_out_obj.browse(data['id'])
        if not [x.id for x in shipment.inventory_moves if x.state == 'draft']:
            return 'end'
        else:
            trans_id = model_data_obj.get_id('stock',
                    'shipmentout_trans_waiting_assigned_force')
            trans = transition_obj.read(trans_id)
            user_in_group = user_group_obj.search([
                    ('user', '=', Transaction().user),
                    ('group', '=', trans['group']),
                    ], limit=1)
            if user_in_group:
                return 'ask_force'
            return 'assign_failed'

    def _moves(self, data):
        shipment_out_obj = Pool().get('stock.shipment.out')
        shipment = shipment_out_obj.browse(data['id'])
        return {'inventory_moves': [x.id for x in shipment.inventory_moves
            if x.state == 'draft']}

    def _force(self, data):
        shipment_out_obj = Pool().get('stock.shipment.out')

        shipment_out_obj.workflow_trigger_validate(data['id'], 'force_assign')
        return {}

AssignShipmentOut()


class ShipmentInternal(ModelWorkflow, ModelSQL, ModelView):
    "Internal Shipment"
    _name = 'stock.shipment.internal'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.Date('Effective Date', readonly=True)
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
            ],
        depends=['state'])
    code = fields.Char("Code", size=None, select=1, readonly=True)
    reference = fields.Char("Reference", size=None, select=1,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    from_location = fields.Many2One('stock.location', "From Location",
        required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('moves'))),
            },
        domain=[
            ('type', 'not in',
                ['supplier', 'customer', 'warehouse', 'view']),
            ], depends=['state', 'moves'])
    to_location = fields.Many2One('stock.location', "To Location",
        required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('moves'))),
            }, domain=[
            ('type', 'not in',
                ['supplier', 'customer', 'warehouse', 'view']),
            ], depends=['state', 'moves'])
    moves = fields.One2Many('stock.move', 'shipment_internal', 'Moves',
        states={
            'readonly': And(Or(Not(Equal(Eval('state'), 'draft')),
                    Not(Bool(Eval('from_location')))),
                Bool(Eval('to_location'))),
            },
        domain=[('company', '=', Eval('company'))],
        context={
            'from_location': Eval('from_location'),
            'to_location': Eval('to_location'),
            'planned_date': Eval('planned_date'),
            },
        depends=['state', 'from_location', 'to_location', 'planned_date',
            'company'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def init(self, module_name):
        cursor = Transaction().cursor
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

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentInternal, self).init(module_name)

        # Migration from 2.0:
        move_obj = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, move_obj._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON shipment.id = move.shipment_internal '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (self._table, move_obj._table))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                self.write(shipment_ids, {'company': company_id})
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def button_draft(self, ids):
        self.workflow_trigger_create(ids)
        return True

    def __init__(self):
        super(ShipmentInternal, self).__init__()
        self._rpc.update({
            'button_draft': True,
        })
        self._order[0] = ('id', 'DESC')

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(
                config.shipment_internal_sequence.id)
        return super(ShipmentInternal, self).create(values)

    def wkf_draft(self, shipment):
        move_obj = Pool().get('stock.move')
        self.write(shipment.id, {
            'state': 'draft',
            })
        move_obj.write([m.id for m in shipment.moves], {
            'state': 'draft',
            })

    def wkf_waiting(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves], {
            'from_location': shipment.from_location.id,
            'to_location': shipment.to_location.id,
            'state': 'draft',
            'planned_date': shipment.planned_date,
            })
        self.write(shipment.id, {
            'state': 'waiting',
            })

    def wkf_assigned(self, shipment):
        self.write(shipment.id, {
            'state': 'assigned',
            })

    def wkf_done(self, shipment):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        move_obj.write([m.id for m in shipment.moves], {
            'state': 'done',
            })
        self.write(shipment.id, {
            'state': 'done',
            'effective_date': date_obj.today(),
            })

    def wkf_cancel(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves], {
            'state': 'cancel',
            })
        self.write(shipment.id, {
            'state': 'cancel',
            })

    def wkf_assign_try(self, shipment):
        move_obj = Pool().get('stock.move')
        return move_obj.assign_try(shipment.moves)

    def wkf_assign_force(self, shipment):
        move_obj = Pool().get('stock.move')
        move_obj.write([m.id for m in shipment.moves], {
            'state': 'assigned',
            })
        return True

ShipmentInternal()


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    delivery = fields.Boolean('Delivery')

Address()


class AssignShipmentInternalAssignFailed(ModelView):
    'Assign Shipment Internal Assign Failed'
    _name = 'stock.shipment.internal.assign.assign_failed'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

AssignShipmentInternalAssignFailed()


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
        'assign_failed': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.internal.assign.assign_failed',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.internal.assign.assign_failed',
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

    def _choice(self, data):
        pool = Pool()
        shipment_internal_obj = pool.get('stock.shipment.internal')
        user_group_obj = pool.get('res.user-res.group')
        model_data_obj = pool.get('ir.model.data')
        transition_obj = pool.get('workflow.transition')

        shipment_internal_obj.workflow_trigger_validate(data['id'], 'assign')
        shipment = shipment_internal_obj.browse(data['id'])
        if not [x.id for x in shipment.moves if x.state == 'draft']:
            return 'end'
        else:
            trans_id = model_data_obj.get_id('stock',
                    'shipmentinternal_trans_waiting_assigned_force')
            trans = transition_obj.read(trans_id)
            user_in_group = user_group_obj.search([
                    ('user', '=', Transaction().user),
                    ('group', '=', trans['group']),
                    ], limit=1)
            if user_in_group:
                return 'ask_force'
            return 'assign_failed'

    def _moves(self, data):
        shipment_internal_obj = Pool().get('stock.shipment.internal')
        shipment = shipment_internal_obj.browse(data['id'])
        return {'moves': [x.id for x in shipment.moves if x.state == 'draft']}

    def _force(self, data):
        shipment_internal_obj = Pool().get('stock.shipment.internal')

        shipment_internal_obj.workflow_trigger_validate(data['id'],
                'force_assign')
        return {}

AssignShipmentInternal()


class AssignShipmentInReturnAssignFailed(ModelView):
    'Assign Supplier Return Shipment Assign Failed'
    _name = 'stock.shipment.in.return.assign.assign_failed'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

AssignShipmentInReturnAssignFailed()


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
        'assign_failed': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.in.return.assign.assign_failed',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'ask_force': {
            'actions': ['_moves'],
            'result': {
                'type': 'form',
                'object': 'stock.shipment.in.return.assign.assign_failed',
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

    def _choice(self, data):
        pool = Pool()
        shipment_internal_obj = pool.get('stock.shipment.in.return')
        user_group_obj = pool.get('res.user-res.group')
        model_data_obj = pool.get('ir.model.data')
        transition_obj = pool.get('workflow.transition')

        shipment_internal_obj.workflow_trigger_validate(data['id'], 'assign')
        shipment = shipment_internal_obj.browse(data['id'])
        if not [x.id for x in shipment.moves if x.state == 'draft']:
            return 'end'
        else:
            trans_id = model_data_obj.get_id('stock',
                    'shipment_in_return_trans_waiting_assigned_force')
            trans = transition_obj.read(trans_id)
            user_in_group = user_group_obj.search([
                    ('user', '=', Transaction().user),
                    ('group', '=', trans['group']),
                    ], limit=1)
            if user_in_group:
                return 'ask_force'
            return 'assign_failed'

    def _moves(self, data):
        shipment_internal_obj = Pool().get('stock.shipment.in.return')
        shipment = shipment_internal_obj.browse(data['id'])
        return {'moves': [x.id for x in shipment.moves if x.state == 'draft']}

    def _force(self, data):
        shipment_internal_obj = Pool().get('stock.shipment.in.return')

        shipment_internal_obj.workflow_trigger_validate(data['id'],
                'force_assign')
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


    def _create(self, data):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        shipment_out_obj = pool.get('stock.shipment.out')
        shipment_out_return_obj = pool.get('stock.shipment.out.return')

        shipment_outs = shipment_out_obj.browse(data['ids'])

        shipment_out_return_ids = []
        for shipment_out in shipment_outs:
            if shipment_out.state != 'done':
                self.raise_user_error('shipment_done_title',
                        error_description='shipment_done_msg',
                        error_description_args=shipment_out.code)

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
                shipment_out_return_obj.create({
                    'customer': shipment_out.customer.id,
                    'delivery_address': shipment_out.delivery_address.id,
                    'warehouse': shipment_out.warehouse.id,
                    'incoming_moves': incoming_moves,
                    })
                )

        act_window_id = model_data_obj.get_id('stock',
                'act_shipment_out_return_form')
        res = act_window_obj.read(act_window_id)
        res['res_id'] = shipment_out_return_ids
        if len(shipment_out_return_ids) == 1:
            res['views'].reverse()

        return res

CreateShipmentOutReturn()


class DeliveryNote(CompanyReport):
    _name = 'stock.shipment.out.delivery_note'

    def parse(self, report, objects, datas, localcontext):
        localcontext['product_name'] = lambda product_id, language: \
                self.product_name(product_id, language)
        return super(DeliveryNote, self).parse(report, objects, datas,
                localcontext)

    def product_name(self, product_id, language):
        product_obj = Pool().get('product.product')
        with Transaction().set_context(language=language):
            return product_obj.browse(product_id).rec_name

DeliveryNote()


class PickingList(CompanyReport):
    _name = 'stock.shipment.out.picking_list'

    def parse(self, report, objects, datas, localcontext):
        compare_context = self.get_compare_context(report, objects, datas)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(PickingList, self).parse(report, objects, datas,
                localcontext)

    def get_compare_context(self, report, objects, datas):
        location_obj = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(list(from_location_ids))
        to_location_ids = location_obj.search(list(to_location_ids))

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

    def parse(self, report, objects, datas, localcontext):
        compare_context = self.get_compare_context(report, objects, datas)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(SupplierRestockingList, self).parse(report, objects,
                datas, localcontext)

    def get_compare_context(self, report, objects, datas):
        location_obj = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(list(from_location_ids))
        to_location_ids = location_obj.search(list(to_location_ids))

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

    def parse(self, report, objects, datas, localcontext):
        compare_context = self.get_compare_context(report, objects, datas)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(CustomerReturnRestockingList, self).parse(report,
                objects, datas, localcontext)

    def get_compare_context(self, report, objects, datas):
        location_obj = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(list(from_location_ids))
        to_location_ids = location_obj.search(list(to_location_ids))

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

    def parse(self, report, objects, datas, localcontext=None):
        compare_context = self.get_compare_context(report, objects, datas)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.moves,
                lambda x,y: cmp(self.get_compare_key(x, compare_context),
                                self.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(InteralShipmentReport, self).parse(report, objects,
                datas, localcontext)

    def get_compare_context(self, report, objects, datas):
        location_obj = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_location_ids = location_obj.search(list(from_location_ids))
        to_location_ids = location_obj.search(list(to_location_ids))

        return {'from_location_ids' : from_location_ids,
                'to_location_ids' : to_location_ids}


    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

InteralShipmentReport()
