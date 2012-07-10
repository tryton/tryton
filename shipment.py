#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import operator
import itertools
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    Button
from trytond.backend import TableHandler
from trytond.pyson import Eval, Not, Equal, If, Or, And, Bool, In, Get, Id
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class ShipmentIn(Workflow, ModelSQL, ModelView):
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
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    supplier = fields.Many2One('party.party', 'Supplier',
        states={
            'readonly': And(Or(Not(Equal(Eval('state'), 'draft')),
                    Bool(Eval('incoming_moves'))), Bool(Eval('supplier'))),
            }, on_change=['supplier'], required=True,
        depends=['state', 'incoming_moves', 'supplier'])
    supplier_location = fields.Function(fields.Many2One('stock.location',
            'Supplier Location', on_change_with=['supplier']),
        'get_supplier_location')
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
    warehouse_input = fields.Function(fields.Many2One('stock.location',
            'Warehouse Input', on_change_with=['warehouse']),
        'get_warehouse_input')
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage', on_change_with=['warehouse']),
        'get_warehouse_storage')
    incoming_moves = fields.Function(fields.One2Many('stock.move', None,
            'Incoming Moves',
            add_remove=[
                ('shipment_in', '=', None),
                ('from_location', '=', Eval('supplier_location')),
                ('state', '=', 'draft'),
                ('to_location', '=', Eval('warehouse_input')),
                ],
            domain=[
                ('from_location', '=', Eval('supplier_location')),
                ('to_location', '=', Eval('warehouse_input')),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': (Eval('state').in_(['received', 'done', 'cancel'])
                    | ~Eval('warehouse') | ~Eval('supplier')),
                },
            depends=['state', 'warehouse', 'supplier_location',
                'warehouse_input', 'company']),
        'get_incoming_moves', setter='set_incoming_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
            'Inventory Moves',
            domain=[
                ('from_location', '=', Eval('warehouse_input')),
                ('to_location', 'child_of', [Eval('warehouse_storage', -1)],
                    'parent'),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': In(Eval('state'), ['draft', 'done', 'cancel']),
                },
            depends=['state', 'warehouse', 'warehouse_input',
                'warehouse_storage', 'company']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_in', 'Moves',
        domain=[('company', '=', Eval('company'))], readonly=True,
        depends=['company'])
    code = fields.Char("Code", size=None, select=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentIn, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'incoming_move_input_dest': 'Incoming Moves must have ' \
                    'the warehouse input location as destination location!',
                'inventory_move_input_source': 'Inventory Moves must ' \
                    'have the warehouse input location as source location!',
                'delete_cancel': 'Supplier Shipment "%s" must be cancelled '\
                    'before deletion!',
                })
        self._transitions |= set((
                ('draft', 'received'),
                ('received', 'done'),
                ('draft', 'cancel'),
                ('received', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                'receive': {
                    'invisible': Eval('state') != 'draft',
                    },
                'done': {
                    'invisible': Eval('state') != 'received',
                    },
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
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
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

    def default_company(self):
        return Transaction().context.get('company')

    def on_change_supplier(self, values):
        if not values.get('supplier'):
            return {'contact_address': None}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['supplier'])
        return {'contact_address': address_id}

    def on_change_with_supplier_location(self, values):
        pool = Pool()
        party_obj = pool.get('party.party')
        if values.get('supplier'):
            supplier = party_obj.browse(values['supplier'])
            return supplier.supplier_location.id

    def get_supplier_location(self, ids, name):
        locations = {}
        for shipment in self.browse(ids):
            locations[shipment.id] = shipment.supplier.supplier_location.id
        return locations

    def default_warehouse_input(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_input({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_input(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.input_location.id

    def get_warehouse_input(self, ids, name):
        inputs = {}
        for shipment in self.browse(ids):
            inputs[shipment.id] = shipment.warehouse.input_location.id
        return inputs

    def default_warehouse_storage(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_storage({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_storage(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.storage_location.id

    def get_warehouse_storage(self, ids, name):
        storages = {}
        for shipment in self.browse(ids):
            storages[shipment.id] = shipment.warehouse.storage_location.id
        return storages

    def get_incoming_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if move.to_location.id == shipment.warehouse.input_location.id:
                    res[shipment.id].append(move.id)
        return res

    def set_incoming_moves(self, ids, name, value):
        if not value:
            return
        self.write(ids, {
            'moves': value,
            })

    def get_inventory_moves(self, ids, name):
        res = {}
        for shipment in self.browse(ids):
            res[shipment.id] = []
            for move in shipment.moves:
                if (move.from_location.id ==
                        shipment.warehouse.input_location.id):
                    res[shipment.id].append(move.id)
        return res

    def set_inventory_moves(self, ids, name, value):
        if not value:
            return
        self.write(ids, {
            'moves': value,
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
        default['inventory_moves'] = None
        default['incoming_moves'] = None
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
        res['planned_date'] = None
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, shipments):
        for shipment in shipments:
            for incoming_move in shipment.incoming_moves:
                vals = self._get_inventory_moves(incoming_move)
                if vals:
                    self.write(shipment.id, {
                        'inventory_moves': [('create', vals)],
                        })

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for shipment in self.browse(ids):
            if shipment.state != 'cancel':
                self.raise_user_error('delete_cancel', shipment.rec_name)
        return super(ShipmentIn, self).delete(ids)

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments
                for m in s.incoming_moves + s.inventory_moves
                if m.state not in ('cancel', 'done')], {
                'state': 'cancel',
                })

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.incoming_moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })
        move_obj.delete([m.id for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

    @ModelView.button
    @Workflow.transition('received')
    def receive(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.incoming_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.create_inventory_moves(shipments)

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.inventory_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

ShipmentIn()


class ShipmentInReturn(Workflow, ModelSQL, ModelView):
    "Supplier Return Shipment"
    _name = 'stock.shipment.in.return'
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
    code = fields.Char("Code", size=None, select=True, readonly=True)
    reference = fields.Char("Reference", size=None, select=True,
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
        domain=[
            ('from_location', '=', Eval('from_location')),
            ('to_location', '=', Eval('to_location')),
            ('company', '=', Eval('company')),
            ],
        depends=['state', 'from_location', 'to_location', 'company'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentInReturn, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'delete_cancel': 'Supplier Return Shipment "%s" must be '\
                    'cancelled before deletion!',
                })
        self._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'assigned'),
                ('waiting', 'draft'),
                ('assigned', 'done'),
                ('assigned', 'waiting'),
                ('draft', 'cancel'),
                ('waiting', 'cancel'),
                ('assigned', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['waiting', 'cancel']),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['assigned', 'draft']),
                    'icon': If(Eval('state') == 'assigned',
                        'tryton-go-previous', 'tryton-go-next'),
                    },
                'done': {
                    'invisible': Eval('state') != 'assigned',
                    },
                'assign_try': {},
                'assign_force': {},
                })

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
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
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_company(self):
        return Transaction().context.get('company')

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

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for shipment in self.browse(ids):
            if shipment.state != 'cancel':
                self.raise_user_error('delete_cancel', shipment.rec_name)
        return super(ShipmentInReturn, self).delete(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })

    @ModelView.button
    @Workflow.transition('waiting')
    def wait(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        for shipment in shipments:
            move_obj.write([m.id for m in shipment.moves
                    if m.state not in ('cancel', 'draft', 'done')], {
                    'state': 'draft',
                    'planned_date': shipment.planned_date,
                    })

    @Workflow.transition('assigned')
    def assign(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('assigned', 'cancel', 'done')], {
                'state': 'assigned',
                })

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('cancel', 'done')], {
                'state': 'cancel',
                })

    @ModelView.button
    def assign_try(self, ids):
        pool = Pool()
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')
        date_obj = pool.get('ir.date')
        move_obj = pool.get('stock.move')

        Transaction().cursor.lock(move_obj._table)

        shipments = self.browse(ids)
        moves = [m for s in shipments for m in s.moves]
        location_ids = [m.from_location.id for m in moves]
        with Transaction().set_context(
                stock_date_end=date_obj.today(),
                stock_assign=True):
            pbl = product_obj.products_by_location(location_ids=location_ids,
                    product_ids=[m.product.id for m in moves])

        for move in moves:
            if move.state != 'draft':
                continue
            if (move.from_location.id, move.product.id) in pbl:
                qty_default_uom = pbl[(move.from_location.id, move.product.id)]
                qty = uom_obj.compute_qty(move.product.default_uom,
                        qty_default_uom, move.uom, round=False)
                if qty < move.quantity:
                    return False
                pbl[(move.from_location.id, move.product.id)] = (
                    pbl[(move.from_location.id, move.product.id)]
                    - qty_default_uom)
            else:
                return False
        self.assign(ids)
        return True

    @ModelView.button
    def assign_force(self, ids):
        self.assign(ids)

ShipmentInReturn()


class ShipmentOut(Workflow, ModelSQL, ModelView):
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
    customer_location = fields.Function(fields.Many2One('stock.location',
            'Customer Location', on_change_with=['customer']),
        'get_customer_location')
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('outgoing_moves'))),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state', 'outgoing_moves'])
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage', on_change_with=['warehouse']),
        'get_warehouse_storage')
    warehouse_output = fields.Function(fields.Many2One('stock.location',
            'Warehouse Output', on_change_with=['warehouse']),
        'get_warehouse_output')
    outgoing_moves = fields.Function(fields.One2Many('stock.move', None,
            'Outgoing Moves',
            domain=[
                ('from_location', '=', Eval('warehouse_output')),
                ('to_location', '=', Eval('customer_location')),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': ((Eval('state').in_(['waiting', 'done', 'cancel']))
                    | ~Eval('warehouse') | ~Eval('customer')),
                },
            depends=['state', 'warehouse', 'customer', 'warehouse_output',
                'customer_location', 'company']),
        'get_outgoing_moves', setter='set_outgoing_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
            'Inventory Moves',
            domain=[
                ('from_location', 'child_of', [Eval('warehouse_storage', -1)],
                    'parent'),
                ('to_location', '=', Eval('warehouse_output')),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': Eval('state').in_(
                    ['draft', 'packed', 'done', 'cancel']),
                },
            depends=['state', 'warehouse', 'warehouse_storage',
                'warehouse_output', 'company']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_out', 'Moves',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        readonly=True)
    code = fields.Char("Code", size=None, select=True, readonly=True)
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
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'delete_cancel': 'Customer Shipment "%s" must be cancelled '\
                    'before deletion!',
                })
        self._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'assigned'),
                ('assigned', 'packed'),
                ('packed', 'done'),
                ('assigned', 'waiting'),
                ('waiting', 'waiting'),
                ('waiting', 'draft'),
                ('draft', 'cancel'),
                ('waiting', 'cancel'),
                ('assigned', 'cancel'),
                ('packed', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['waiting', 'cancel']),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['assigned', 'waiting',
                            'draft']),
                    'icon': If(Eval('state') == 'assigned',
                        'tryton-go-previous',
                        If(Eval('state') == 'waiting',
                            'tryton-clear',
                            'tryton-go-next')),
                    },
                'pack': {
                    'invisible': Eval('state') != 'assigned',
                    },
                'done': {
                    'invisible': Eval('state') != 'packed',
                    },
                'assign_try': {},
                'assign_force': {},
                })

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
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
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
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

    def default_company(self):
        return Transaction().context.get('company')

    def on_change_customer(self, values):
        if not values.get('customer'):
            return {'delivery_address': None}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['customer'], type='delivery')
        return {'delivery_address': address_id}

    def on_change_with_customer_location(self, values):
        pool = Pool()
        party_obj = pool.get('party.party')
        if values.get('customer'):
            customer = party_obj.browse(values['customer'])
            return customer.customer_location.id

    def get_customer_location(self, ids, name):
        locations = {}
        for shipment in self.browse(ids):
            locations[shipment.id] = shipment.customer.customer_location.id
        return locations

    def default_warehouse_storage(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_storage({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_storage(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.storage_location.id

    def get_warehouse_storage(self, ids, name):
        storages = {}
        for shipment in self.browse(ids):
            storages[shipment.id] = shipment.warehouse.storage_location.id
        return storages

    def default_warehouse_output(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_output({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_output(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.output_location.id

    def get_warehouse_output(self, ids, name):
        outputs = {}
        for shipment in self.browse(ids):
            outputs[shipment.id] = shipment.warehouse.output_location.id
        return outputs

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
        if not value:
            return
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
        if not value:
            return
        self.write(ids, {
            'moves': value,
            })

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments
                for m in s.inventory_moves + s.outgoing_moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })

    @ModelView.button
    @Workflow.transition('waiting')
    def wait(self, ids):
        """
        Complete inventory moves to match the products and quantities
        that are in the outgoing moves.
        """
        move_obj = Pool().get('stock.move')

        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.inventory_moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })
        move_obj.delete([m.id for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

        # Re-Browse because moves have been deleted
        shipments = self.browse(ids)

        for shipment in shipments:
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

    @Workflow.transition('assigned')
    def assign(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('packed')
    def pack(self, ids):
        move_obj = Pool().get('stock.move')
        uom_obj = Pool().get('product.uom')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.inventory_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })

        for shipment in shipments:
            # Sum all outgoing quantities
            outgoing_qty = {}
            for move in shipment.outgoing_moves:
                if move.state == 'cancel':
                    continue
                quantity = uom_obj.compute_qty(move.uom, move.quantity,
                        move.product.default_uom, round=False)
                outgoing_qty.setdefault(move.product.id, 0.0)
                outgoing_qty[move.product.id] += quantity

            for move in shipment.inventory_moves:
                if move.state == 'cancel':
                    continue
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
                        out_quantity = (qty_default_uom
                            - outgoing_qty[move.product.id])
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
                if move.state == 'cancel':
                    continue
                if outgoing_qty.get(move.product.id, 0.0) > 0.0:
                    exc_qty = uom_obj.compute_qty(move.product.default_uom,
                            outgoing_qty[move.product.id], move.uom)
                    removed_qty = uom_obj.compute_qty(move.uom,
                        min(exc_qty, move.quantity), move.product.default_uom,
                        round=False)
                    move_obj.write(move.id, {
                            'quantity': max(0.0, move.quantity - exc_qty),
                            })
                    outgoing_qty[move.product.id] -= removed_qty

        move_obj.write([m.id for s in shipments for m in s.outgoing_moves
                if m.state not in ('cancel', 'done')], {
                'state': 'assigned',
                })

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')

        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.outgoing_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments
                for m in s.outgoing_moves + s.inventory_moves
                if m.state not in ('cancel', 'done')], {
                'state': 'cancel',
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
        default['inventory_moves'] = None
        default['outgoing_moves'] = None
        return super(ShipmentOut, self).copy(ids, default=default)

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for shipment in self.browse(ids):
            if shipment.state != 'cancel':
                self.raise_user_error('delete_cancel', shipment.rec_name)
        return super(ShipmentOut, self).delete(ids)

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

    @ModelView.button
    def assign_try(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        if move_obj.assign_try([m for s in shipments
                    for m in s.inventory_moves]):
            self.assign(ids)
            return True
        else:
            return False

    @ModelView.button
    def assign_force(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.inventory_moves
                if m.state not in ('cancel', 'done')], {
                'state': 'assigned',
                })
        self.assign(ids)

ShipmentOut()


class ShipmentOutReturn(Workflow, ModelSQL, ModelView):
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
    customer_location = fields.Function(fields.Many2One('stock.location',
            'Customer Location', on_change_with=['customer']),
        'get_customer_location')
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('incoming_moves'))),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state', 'incoming_moves'])
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage', on_change_with=['warehouse']),
        'get_warehouse_storage')
    warehouse_input = fields.Function(fields.Many2One('stock.location',
            'Warehouse Input', on_change_with=['warehouse']),
        'get_warehouse_input')
    incoming_moves = fields.Function(fields.One2Many('stock.move', None,
            'Incoming Moves',
            domain=[
                ('from_location', '=', Eval('customer_location')),
                ('to_location', '=', Eval('warehouse_input')),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': ((Eval('state') != 'draft')
                    | ~Eval('warehouse') | ~Eval('customer')),
                },
            depends=['state', 'warehouse', 'customer', 'customer_location',
                'warehouse_input', 'company']),
        'get_incoming_moves', setter='set_incoming_moves')
    inventory_moves = fields.Function(fields.One2Many('stock.move', None,
            'Inventory Moves',
            domain=[
                ('from_location', '=', Eval('warehouse_input')),
                ('to_location', 'child_of', [Eval('warehouse_storage', -1)],
                    'parent'),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': Eval('state').in_(['draft', 'cancel', 'done']),
                },
            depends=['state', 'warehouse', 'warehouse_input',
                'warehouse_storage', 'company']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment_out_return', 'Moves',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        readonly=True)
    code = fields.Char("Code", size=None, select=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentOutReturn, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'delete_cancel': 'Customer Return Shipment "%s" must be '\
                    'cancelled before deletion!',
                })
        self._transitions |= set((
                ('draft', 'received'),
                ('received', 'done'),
                ('received', 'draf'),
                ('draft', 'cancel'),
                ('received', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                'receive': {
                    'invisible': Eval('state') != 'draft',
                    },
                'done': {
                    'invisible': Eval('state') != 'received',
                    },
                })

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
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
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
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

    def default_company(self):
        return Transaction().context.get('company')

    def on_change_customer(self, values):
        if not values.get('customer'):
            return {'delivery_address': None}
        party_obj = Pool().get("party.party")
        address_id = party_obj.address_get(values['customer'], type='delivery')
        return {
                'delivery_address': address_id,
            }

    def on_change_with_customer_location(self, values):
        pool = Pool()
        party_obj = pool.get('party.party')
        if values.get('customer'):
            customer = party_obj.browse(values['customer'])
            return customer.customer_location.id

    def get_customer_location(self, ids, name):
        locations = {}
        for shipment in self.browse(ids):
            locations[shipment.id] = shipment.customer.customer_location.id
        return locations

    def default_warehouse_storage(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_storage({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_storage(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.storage_location.id

    def get_warehouse_storage(self, ids, name):
        storages = {}
        for shipment in self.browse(ids):
            storages[shipment.id] = shipment.warehouse.storage_location.id
        return storages

    def default_warehouse_input(self):
        warehouse = self.default_warehouse()
        if warehouse:
            value = self.on_change_with_warehouse_input({
                    'warehouse': warehouse,
                    })
            return value

    def on_change_with_warehouse_input(self, values):
        pool = Pool()
        location_obj = pool.get('stock.location')
        if values.get('warehouse'):
            warehouse = location_obj.browse(values['warehouse'])
            return warehouse.input_location.id

    def get_warehouse_input(self, ids, name):
        inputs = {}
        for shipment in self.browse(ids):
            inputs[shipment.id] = shipment.warehouse.input_location.id
        return inputs

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
        if not value:
            return
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
        if not value:
            return
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
            move_obj.write([x.id for x in shipment.inventory_moves
                    if x.state not in ('assigned', 'done', 'cancel')], {
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
        default['inventory_moves'] = None
        default['incoming_moves'] = None
        return super(ShipmentOutReturn, self).copy(ids, default=default)

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cance before delete
        self.cancel(ids)
        for shipment in self.browse(ids):
            if shipment.state != 'cancel':
                self.raise_user_error('delete_cancel', shipment.rec_name)
        return super(ShipmentOutReturn, self).delete(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.incoming_moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })
        move_obj.delete([m.id for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

    @ModelView.button
    @Workflow.transition('received')
    def receive(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.incoming_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.create_inventory_moves(shipments)

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.inventory_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments
                for m in s.incoming_moves + s.inventory_moves
                if m.state not in ('cancel', 'done')], {
                'state': 'cancel',
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
        res['planned_date'] = None
        res['company'] = incoming_move.company.id
        return res

    def create_inventory_moves(self, shipments):
        for shipment in shipments:
            for incoming_move in shipment.incoming_moves:
                vals = self._get_inventory_moves(incoming_move)
                if vals:
                    self.write(shipment.id, {
                        'inventory_moves': [('create', vals)],
                        })

ShipmentOutReturn()


class AssignShipmentOutAssignFailed(ModelView):
    'Assign Shipment Out'
    _name = 'stock.shipment.out.assign.failed'
    _description = __doc__

    inventory_moves = fields.Many2Many('stock.move', None, None,
            'Inventory Moves', readonly=True)

    def default_inventory_moves(self):
        shipment_out_obj = Pool().get('stock.shipment.out')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = shipment_out_obj.browse(shipment_id)
        return [x.id for x in shipment.inventory_moves if x.state == 'draft']

AssignShipmentOutAssignFailed()


class AssignShipmentOut(Wizard):
    'Assign Shipment Out'
    _name = 'stock.shipment.out.assign'

    start = StateTransition()
    failed = StateView('stock.shipment.out.assign.failed',
        'stock.shipment_out_assign_failed_view_form', [
            Button('Force Assign', 'force', 'tryton-go-next',
                states={
                    'invisible': ~Id('stock',
                        'group_stock_force_assignment').in_(
                        Eval('context', {}).get('groups', [])),
                    }),
            Button('Ok', 'end', 'tryton-ok', True),
            ])
    force = StateTransition()

    def transition_start(self, session):
        pool = Pool()
        shipment_obj = pool.get('stock.shipment.out')

        if shipment_obj.assign_try([Transaction().context['active_id']]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self, session):
        shipment_obj = Pool().get('stock.shipment.out')

        shipment_obj.assign_force([Transaction().context['active_id']])
        return 'end'

AssignShipmentOut()


class ShipmentInternal(Workflow, ModelSQL, ModelView):
    "Internal Shipment"
    _name = 'stock.shipment.internal'
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
    code = fields.Char("Code", size=None, select=True, readonly=True)
    reference = fields.Char("Reference", size=None, select=True,
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
            'readonly': ((Eval('state') != 'draft')
                | ~Eval('from_location') | ~Eval('to_location')),
            },
        domain=[
            ('from_location', '=', Eval('from_location')),
            ('to_location', '=', Eval('to_location')),
            ('company', '=', Eval('company')),
            ],
        depends=['state', 'from_location', 'to_location', 'planned_date',
            'company'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Canceled'),
        ('assigned', 'Assigned'),
        ('waiting', 'Waiting'),
        ('done', 'Done'),
        ], 'State', readonly=True)

    def __init__(self):
        super(ShipmentInternal, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'delete_cancel': 'Internal Shipment "%s" must be cancelled '\
                    'before deletion!',
                })
        self._transitions |= set((
                ('draft', 'waiting'),
                ('waiting', 'waiting'),
                ('waiting', 'assigned'),
                ('assigned', 'done'),
                ('waiting', 'draft'),
                ('assigned', 'waiting'),
                ('draft', 'cancel'),
                ('waiting', 'cancel'),
                ('assigned', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'waiting']),
                    'icon': If(Eval('state') == 'cancel',
                        'tryton-clear',
                        'tryton-go-previous'),
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['assigned', 'waiting',
                            'draft']),
                    'icon': If(Eval('state') == 'assigned',
                        'tryton-go-previous',
                        If(Eval('state') == 'waiting',
                            'tryton-clear',
                            'tryton-go-next')),
                    },
                'done': {
                    'invisible': Eval('state') != 'assigned',
                    },
                'assign_try': {},
                'assign_force': {},
                })

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
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
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + self._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, self, module_name)
        table.index_action('create_date', action='add')

    def default_state(self):
        return 'draft'

    def default_company(self):
        return Transaction().context.get('company')

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('stock.configuration')

        values = values.copy()
        config = config_obj.browse(1)
        values['code'] = sequence_obj.get_id(
                config.shipment_internal_sequence.id)
        return super(ShipmentInternal, self).create(values)

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for shipment in self.browse(ids):
            if shipment.state != 'cancel':
                self.raise_user_error('delete_cancel', shipment.rec_name)
        return super(ShipmentInternal, self).delete(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })

    @ModelView.button
    @Workflow.transition('waiting')
    def wait(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        # First reset state to draft to allow update from and to location
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('draft', 'done')], {
                'state': 'draft',
                })
        for shipment in shipments:
            move_obj.write([m.id for m in shipment.moves
                    if m.state != 'done'], {
                'from_location': shipment.from_location.id,
                'to_location': shipment.to_location.id,
                'planned_date': shipment.planned_date,
                })

    @Workflow.transition('assigned')
    def assign(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('done')
    def done(self, ids):
        move_obj = Pool().get('stock.move')
        date_obj = Pool().get('ir.date')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('done', 'cancel')], {
                'state': 'done',
                })
        self.write(ids, {
                'effective_date': date_obj.today(),
                })

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('cancel', 'done')], {
                'state': 'cancel',
                })

    @ModelView.button
    def assign_try(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        if move_obj.assign_try([m for s in shipments
                    for m in s.moves]):
            self.assign(ids)
            return True
        else:
            return False

    @ModelView.button
    def assign_force(self, ids):
        move_obj = Pool().get('stock.move')
        shipments = self.browse(ids)
        move_obj.write([m.id for s in shipments for m in s.moves
                if m.state not in ('assigned', 'done')], {
                'state': 'assigned',
                })
        self.assign(ids)

ShipmentInternal()


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    delivery = fields.Boolean('Delivery')

Address()


class AssignShipmentInternalAssignFailed(ModelView):
    'Assign Shipment Internal'
    _name = 'stock.shipment.internal.assign.failed'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

    def default_moves(self):
        shipment_internal_obj = Pool().get('stock.shipment.internal')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = shipment_internal_obj.browse(shipment_id)
        return [x.id for x in shipment.moves if x.state == 'draft']

AssignShipmentInternalAssignFailed()


class AssignShipmentInternal(Wizard):
    'Assign Shipment Internal'
    _name = 'stock.shipment.internal.assign'

    start = StateTransition()
    failed = StateView('stock.shipment.internal.assign.failed',
        'stock.shipment_internal_assign_failed_view_form', [
            Button('Force Assign', 'force', 'tryton-go-next',
                states={
                    'invisible': ~Id('stock',
                        'group_stock_force_assignment').in_(
                        Eval('context', {}).get('groups', [])),
                    }),
            Button('Ok', 'end', 'tryton-ok', True),
            ])
    force = StateTransition()

    def transition_start(self, session):
        pool = Pool()
        shipment_obj = pool.get('stock.shipment.internal')

        if shipment_obj.assign_try([Transaction().context['active_id']]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self, session):
        shipment_obj = Pool().get('stock.shipment.internal')

        shipment_obj.assign_force([Transaction().context['active_id']])
        return 'end'

AssignShipmentInternal()


class AssignShipmentInReturnAssignFailed(ModelView):
    'Assign Supplier Return Shipment'
    _name = 'stock.shipment.in.return.assign.failed'
    _description = __doc__

    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

    def default_moves(self):
        shipment_internal_obj = Pool().get('stock.shipment.in.return')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = shipment_internal_obj.browse(shipment_id)
        return [x.id for x in shipment.moves if x.state == 'draft']

AssignShipmentInReturnAssignFailed()


class AssignShipmentInReturn(Wizard):
    'Assign Supplier Return Shipment'
    _name = 'stock.shipment.in.return.assign'

    start = StateTransition()
    failed = StateView('stock.shipment.in.return.assign.failed',
        'stock.shipment_in_return_assign_failed_view_form', [
            Button('Force Assign', 'force', 'tryton-go-next',
                states={
                    'invisible': ~Id('stock',
                        'group_stock_force_assignment').in_(
                        Eval('context', {}).get('groups', [])),
                }),
            Button('Ok', 'end', 'tryton-ok', True),
            ])
    force = StateTransition()

    def transition_start(self, session):
        pool = Pool()
        shipment_obj = pool.get('stock.shipment.in.return')

        if shipment_obj.assign_try([Transaction().context['active_id']]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self, session):
        shipment_obj = Pool().get('stock.shipment.in.return')

        shipment_obj.assign_force([Transaction().context['active_id']])
        return 'end'

AssignShipmentInReturn()


class CreateShipmentOutReturn(Wizard):
    'Create Customer Return Shipment'
    _name = 'stock.shipment.out.return.create'

    start = StateAction('stock.act_shipment_out_return_form')

    def __init__(self):
        super(CreateShipmentOutReturn, self).__init__()
        self._error_messages.update({
            'shipment_done_title': 'You can not create return shipment',
            'shipment_done_msg': 'The shipment with code %s is not yet sent.',
            })

    def do_start(self, session, action):
        pool = Pool()
        shipment_out_obj = pool.get('stock.shipment.out')
        shipment_out_return_obj = pool.get('stock.shipment.out.return')

        shipment_ids = Transaction().context['active_ids']
        shipment_outs = shipment_out_obj.browse(shipment_ids)

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
                            'to_location': \
                                shipment_out.warehouse.input_location.id,
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

        data = {'res_id': shipment_out_return_ids}
        if len(shipment_out_return_ids) == 1:
            action['views'].reverse()
        return action, data

    def transition_start(self, session):
        return 'end'

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
                lambda x, y: cmp(self.get_compare_key(x, compare_context),
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

        return {
            'from_location_ids': from_location_ids,
            'to_location_ids': to_location_ids,
            }

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
                lambda x, y: cmp(self.get_compare_key(x, compare_context),
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

        return {
            'from_location_ids': from_location_ids,
            'to_location_ids': to_location_ids,
            }

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
                lambda x, y: cmp(self.get_compare_key(x, compare_context),
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

        return {
            'from_location_ids': from_location_ids,
            'to_location_ids': to_location_ids,
            }

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
                lambda x, y: cmp(self.get_compare_key(x, compare_context),
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

        return {
            'from_location_ids': from_location_ids,
            'to_location_ids': to_location_ids,
            }

    def get_compare_key(self, move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]

InteralShipmentReport()
