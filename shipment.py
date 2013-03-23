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
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids

__all__ = ['ShipmentIn', 'ShipmentInReturn',
    'ShipmentOut', 'ShipmentOutReturn',
    'AssignShipmentOutAssignFailed', 'AssignShipmentOut',
    'ShipmentInternal',
    'Address',
    'AssignShipmentInternalAssignFailed', 'AssignShipmentInternal',
    'AssignShipmentInReturnAssignFailed', 'AssignShipmentInReturn',
    'CreateShipmentOutReturn',
    'DeliveryNote', 'PickingList',
    'SupplierRestockingList', 'CustomerReturnRestockingList',
    'InteralShipmentReport']
__metaclass__ = PoolMeta

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class ShipmentIn(Workflow, ModelSQL, ModelView):
    "Supplier Shipment"
    __name__ = 'stock.shipment.in'
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
        'on_change_with_supplier_location')
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
        'on_change_with_warehouse_input')
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage', on_change_with=['warehouse']),
        'on_change_with_warehouse_storage')
    incoming_moves = fields.Function(fields.One2Many('stock.move', None,
            'Incoming Moves',
            add_remove=[
                ('shipment', '=', None),
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
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        domain=[('company', '=', Eval('company'))], readonly=True,
        depends=['company'])
    code = fields.Char("Code", size=None, select=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ShipmentIn, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'incoming_move_input_dest': ('Incoming Moves must have '
                    'the warehouse input location as destination location.'),
                'inventory_move_input_source': ('Inventory Moves must '
                    'have the warehouse input location as source location.'),
                'delete_cancel': ('Supplier Shipment "%s" must be cancelled '
                    'before deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'received'),
                ('received', 'done'),
                ('draft', 'cancel'),
                ('received', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
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

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "
            "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "
            "WHERE fs_id like '%%packing%%' AND module = %s",
            (module_name,))
        cursor.execute("UPDATE ir_model "
            "SET model = REPLACE(model, 'packing', 'shipment') "
            "WHERE model like '%%packing%%' AND module = %s",
            (module_name,))
        cursor.execute("UPDATE ir_model_field "
            "SET relation = REPLACE(relation, 'packing', 'shipment'), "
                "name = REPLACE(name, 'packing', 'shipment') "
            "WHERE (relation like '%%packing%%' "
                "OR name like '%%packing%%') AND module = %s",
            (module_name,))

        old_table = 'stock_packing_in'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, cls._table)
        table = TableHandler(cursor, cls, module_name)
        for field in ('create_uid', 'write_uid', 'contact_address',
                'warehouse', 'supplier'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentIn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, Move._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON \'%s,\' || shipment.id = move.shipment '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (cls._table, Move._table, cls.__name__))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def on_change_supplier(self):
        if not self.supplier:
            return {'contact_address': None}
        address = self.supplier.address_get()
        return {'contact_address': address.id}

    def on_change_with_supplier_location(self, name=None):
        if self.supplier:
            return self.supplier.supplier_location.id

    @classmethod
    def default_warehouse_input(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_input()

    def on_change_with_warehouse_input(self, name=None):
        if self.warehouse:
            return self.warehouse.input_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    def on_change_with_warehouse_storage(self, name=None):
        if self.warehouse:
            return self.warehouse.storage_location.id

    def get_incoming_moves(self, name):
        moves = []
        for move in self.moves:
            if move.to_location.id == self.warehouse.input_location.id:
                moves.append(move.id)
        return moves

    @classmethod
    def set_incoming_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    def get_inventory_moves(self, name):
        moves = []
        for move in self.moves:
            if (move.from_location.id ==
                    self.warehouse.input_location.id):
                moves.append(move.id)
        return moves

    @classmethod
    def set_inventory_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    @property
    def _move_planned_date(self):
        '''
        Return the planned date for incoming moves and inventory_moves
        '''
        return self.planned_date, self.planned_date

    @classmethod
    def _set_move_planned_date(cls, shipments):
        '''
        Set planned date of moves for the shipments
        '''
        Move = Pool().get('stock.move')
        for shipment in shipments:
            dates = shipment._move_planned_date
            incoming_date, inventory_date = dates
            Move.write([m for m in shipment.incoming_moves
                    if (m.state not in ('assigned', 'done', 'cancel')
                        and m.planned_date != incoming_date)], {
                    'planned_date': incoming_date,
                    })
            Move.write([m for m in shipment.inventory_moves
                    if (m.state not in ('assigned', 'done', 'cancel')
                        and m.planned_date != inventory_date)], {
                    'planned_date': inventory_date,
                    })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(config.shipment_in_sequence)
        shipments = super(ShipmentIn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, shipments, values):
        super(ShipmentIn, cls).write(shipments, values)
        cls._set_move_planned_date(shipments)

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves'] = None
        default['incoming_moves'] = None
        return super(ShipmentIn, cls).copy(shipments, default=default)

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        pool = Pool()
        Move = pool.get('stock.move')
        if incoming_move.quantity <= 0.0:
            return None
        move = Move()
        move.product = incoming_move.product
        move.uom = incoming_move.uom
        move.quantity = incoming_move.quantity
        move.from_location = incoming_move.to_location
        move.to_location = incoming_move.shipment.warehouse.storage_location
        move.state = Move.default_state()
        # Product will be considered in stock only when the inventory
        # move will be made:
        move.planned_date = None
        move.company = incoming_move.company
        return move

    @classmethod
    def create_inventory_moves(cls, shipments):
        for shipment in shipments:
            # Use moves instead of inventory_moves because save reset before
            # adding new records and as set_inventory_moves is just a proxy to
            # moves, it will reset also the incoming_moves
            moves = list(shipment.moves)
            for incoming_move in shipment.incoming_moves:
                move = cls._get_inventory_moves(incoming_move)
                if move:
                    moves.append(move)
            shipment.moves = moves
            shipment.save()

    @classmethod
    def delete(cls, shipments):
        Move = Pool().get('stock.move')
        # Cancel before delete
        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', shipment.rec_name)
        Move.delete([m for s in shipments for m in s.moves])
        super(ShipmentIn, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments
                for m in s.incoming_moves + s.inventory_moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments for m in s.incoming_moves])
        Move.delete([m for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        Move = Pool().get('stock.move')
        Move.do([m for s in shipments for m in s.incoming_moves])
        cls.create_inventory_moves(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for s in shipments for m in s.inventory_moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })


class ShipmentInReturn(Workflow, ModelSQL, ModelView):
    "Supplier Return Shipment"
    __name__ = 'stock.shipment.in.return'
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
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
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

    @classmethod
    def __setup__(cls):
        super(ShipmentInReturn, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'delete_cancel': ('Supplier Return Shipment "%s" must be '
                    'cancelled before deletion.'),
                })
        cls._transitions |= set((
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
        cls._buttons.update({
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
                'assign_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'readonly': ~Eval('groups', []).contains(
                        Id('stock', 'group_stock')),
                    },
                'assign_try': {},
                'assign_force': {},
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_in_return'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, cls._table)
        table = TableHandler(cursor, cls, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentInReturn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, Move._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON \'%s,\' || shipment.id = move.shipment '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (cls._table, Move._table, cls.__name__))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @property
    def _move_planned_date(self):
        '''
        Return the planned date for the moves
        '''
        return self.planned_date

    @classmethod
    def _set_move_planned_date(cls, shipments):
        '''
        Set planned date of moves for the shipments
        '''
        Move = Pool().get('stock.move')
        for shipment in shipments:
            Move.write([m for m in shipment.moves
                    if (m.state not in ('assigned', 'done', 'cancel')
                        and m.planned_date != shipment._move_planned_date)], {
                    'planned_date': shipment._move_planned_date,
                    })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(
                config.shipment_in_return_sequence.id)
        shipments = super(ShipmentInReturn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, shipments, values):
        super(ShipmentInReturn, cls).write(shipments, values)
        cls._set_move_planned_date(shipments)

    @classmethod
    def delete(cls, shipments):
        Move = Pool().get('stock.move')
        # Cancel before delete
        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', shipment.rec_name)
        Move.delete([m for s in shipments for m in s.moves])
        super(ShipmentInReturn, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments for m in s.moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments):
        Move = Pool().get('stock.move')
        for shipment in shipments:
            Move.draft([m for m in shipment.moves])
        cls._set_move_planned_date(shipments)

    @classmethod
    @Workflow.transition('assigned')
    def assign(cls, shipments):
        Move = Pool().get('stock.move')
        Move.assign([m for s in shipments for m in s.moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        Move.do([m for s in shipments for m in s.moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments for m in s.moves])

    @classmethod
    @ModelView.button_action('stock.wizard_shipment_in_return_assign')
    def assign_wizard(cls, shipments):
        pass

    @classmethod
    @ModelView.button
    def assign_try(cls, shipments):
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')

        Transaction().cursor.lock(Move._table)

        moves = [m for s in shipments for m in s.moves]
        location_ids = [m.from_location.id for m in moves]
        with Transaction().set_context(
                stock_date_end=Date.today(),
                stock_assign=True):
            pbl = Product.products_by_location(location_ids=location_ids,
                product_ids=[m.product.id for m in moves])

        for move in moves:
            if move.state != 'draft':
                continue
            if (move.from_location.id, move.product.id) in pbl:
                qty_default_uom = pbl[(move.from_location.id, move.product.id)]
                qty = Uom.compute_qty(move.product.default_uom,
                    qty_default_uom, move.uom, round=False)
                if qty < move.quantity:
                    return False
                pbl[(move.from_location.id, move.product.id)] = (
                    pbl[(move.from_location.id, move.product.id)]
                    - qty_default_uom)
            else:
                return False
        cls.assign(shipments)
        return True

    @classmethod
    @ModelView.button
    def assign_force(cls, shipments):
        cls.assign(shipments)


class ShipmentOut(Workflow, ModelSQL, ModelView):
    "Customer Shipment"
    __name__ = 'stock.shipment.out'
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
        'on_change_with_customer_location')
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
        'on_change_with_warehouse_storage')
    warehouse_output = fields.Function(fields.Many2One('stock.location',
            'Warehouse Output', on_change_with=['warehouse']),
        'on_change_with_warehouse_output')
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
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
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

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'delete_cancel': ('Customer Shipment "%s" must be cancelled '
                    'before deletion.'),
                })
        cls._transitions |= set((
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
        cls._buttons.update({
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
                'assign_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'readonly': ~Eval('groups', []).contains(
                        Id('stock', 'group_stock')),
                    },
                'assign_try': {},
                'assign_force': {},
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_out'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, cls._table)

        table = TableHandler(cursor, cls, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentOut, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, Move._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON \'%s,\' || shipment.id = move.shipment '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (cls._table, Move._table, cls.__name__))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Migration from 1.0 customer_location is no more used
        table = TableHandler(cursor, cls, module_name)
        table.drop_column('customer_location', exception=True)

        # Add index on create_date
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def on_change_customer(self):
        if not self.customer:
            return {'delivery_address': None}
        address = self.customer.address_get(type='delivery')
        return {'delivery_address': address.id}

    def on_change_with_customer_location(self, name=None):
        if self.customer:
            return self.customer.customer_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    def on_change_with_warehouse_storage(self, name=None):
        if self.warehouse:
            return self.warehouse.storage_location.id

    @classmethod
    def default_warehouse_output(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_output()

    def on_change_with_warehouse_output(self, name=None):
        if self.warehouse:
            return self.warehouse.output_location.id

    def get_outgoing_moves(self, name):
        moves = []
        for move in self.moves:
            if move.from_location.id == self.warehouse.output_location.id:
                moves.append(move.id)
        return moves

    @classmethod
    def set_outgoing_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    def get_inventory_moves(self, name):
        moves = []
        for move in self.moves:
            if move.to_location.id == self.warehouse.output_location.id:
                moves.append(move.id)
        return moves

    @classmethod
    def set_inventory_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments
                for m in s.inventory_moves + s.outgoing_moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments):
        """
        Complete inventory moves to match the products and quantities
        that are in the outgoing moves.
        """
        Move = Pool().get('stock.move')

        Move.draft([m for s in shipments for m in s.inventory_moves])
        Move.delete([m for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

        to_create = []
        for shipment in shipments:
            for move in shipment.outgoing_moves:
                if move.state in ('cancel', 'done'):
                    continue
                to_create.append({
                        'from_location': (
                            move.shipment.warehouse.storage_location.id),
                        'to_location': move.from_location.id,
                        'product': move.product.id,
                        'uom': move.uom.id,
                        'quantity': move.quantity,
                        'shipment': str(shipment),
                        'planned_date': move.planned_date,
                        'state': 'draft',
                        'company': move.company.id,
                        'currency': move.currency.id,
                        'unit_price': move.unit_price,
                        })
        if to_create:
            Move.create(to_create)

    @classmethod
    @Workflow.transition('assigned')
    def assign(cls, shipments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        Move.do([m for s in shipments for m in s.inventory_moves])

        for shipment in shipments:
            # Sum all outgoing quantities
            outgoing_qty = {}
            for move in shipment.outgoing_moves:
                if move.state == 'cancel':
                    continue
                quantity = Uom.compute_qty(move.uom, move.quantity,
                        move.product.default_uom, round=False)
                outgoing_qty.setdefault(move.product.id, 0.0)
                outgoing_qty[move.product.id] += quantity

            to_create = []
            for move in shipment.inventory_moves:
                if move.state == 'cancel':
                    continue
                qty_default_uom = Uom.compute_qty(move.uom, move.quantity,
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
                        out_quantity = Uom.compute_qty(
                            move.product.default_uom, out_quantity, move.uom)
                        outgoing_qty[move.product.id] = 0.0
                else:
                    out_quantity = move.quantity

                unit_price = Uom.compute_price(move.product.default_uom,
                        move.product.list_price, move.uom)
                to_create.append({
                        'from_location': move.to_location.id,
                        'to_location': shipment.customer.customer_location.id,
                        'product': move.product.id,
                        'uom': move.uom.id,
                        'quantity': out_quantity,
                        'shipment': str(shipment),
                        'state': 'draft',
                        'planned_date': shipment.planned_date,
                        'company': move.company.id,
                        'currency': move.company.currency.id,
                        'unit_price': unit_price,
                        })
            if to_create:
                Move.create(to_create)

            #Re-read the shipment and remove exceeding quantities
            for move in shipment.outgoing_moves:
                if move.state == 'cancel':
                    continue
                if outgoing_qty.get(move.product.id, 0.0) > 0.0:
                    exc_qty = Uom.compute_qty(move.product.default_uom,
                            outgoing_qty[move.product.id], move.uom)
                    removed_qty = Uom.compute_qty(move.uom,
                        min(exc_qty, move.quantity), move.product.default_uom,
                        round=False)
                    Move.write([move], {
                            'quantity': max(0.0, move.quantity - exc_qty),
                            })
                    outgoing_qty[move.product.id] -= removed_qty

        Move.assign([m for s in shipments for m in s.outgoing_moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        Move.do([m for s in shipments for m in s.outgoing_moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments
                for m in s.outgoing_moves + s.inventory_moves])

    @property
    def _move_planned_date(self):
        '''
        Return the planned date for outgoing moves and inventory moves
        '''
        return self.planned_date, self.planned_date

    @classmethod
    def _set_move_planned_date(self, shipments):
        '''
        Set planned date of moves for the shipments
        '''
        Move = Pool().get('stock.move')
        for shipment in shipments:
            outgoing_date, inventory_date = shipment._move_planned_date
            Move.write([x for x in shipment.outgoing_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != outgoing_date)], {
                    'planned_date': outgoing_date,
                    })
            Move.write([x for x in shipment.inventory_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != inventory_date)], {
                    'planned_date': inventory_date,
                    })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(config.shipment_out_sequence.id)
        shipments = super(ShipmentOut, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, shipments, values):
        super(ShipmentOut, cls).write(shipments, values)
        cls._set_move_planned_date(shipments)

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves'] = None
        default['outgoing_moves'] = None
        return super(ShipmentOut, cls).copy(shipments, default=default)

    @classmethod
    def delete(cls, shipments):
        Move = Pool().get('stock.move')
        # Cancel before delete
        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', shipment.rec_name)
        Move.delete([m for s in shipments for m in s.moves])
        super(ShipmentOut, cls).delete(shipments)

    @staticmethod
    def _location_amount(target_uom, qty_uom, uom_index):
        """
        Take a raw list of quantities and uom and convert it to
        the target uom.
        """
        Uom = Pool().get('product.uom')
        res = 0
        for uom, qty in qty_uom:
            res += Uom.compute_qty(uom_index[uom], qty,
                    uom_index[target_uom])
        return res

    @classmethod
    @ModelView.button_action('stock.wizard_shipment_out_assign')
    def assign_wizard(cls, shipments):
        pass

    @classmethod
    @ModelView.button
    def assign_try(cls, shipments):
        Move = Pool().get('stock.move')
        if Move.assign_try([m for s in shipments
                    for m in s.inventory_moves]):
            cls.assign(shipments)
            return True
        else:
            return False

    @classmethod
    @ModelView.button
    def assign_force(cls, shipments):
        Move = Pool().get('stock.move')
        Move.assign([m for s in shipments for m in s.inventory_moves])
        cls.assign(shipments)


class ShipmentOutReturn(Workflow, ModelSQL, ModelView):
    "Customer Return Shipment"
    __name__ = 'stock.shipment.out.return'
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
        'on_change_with_customer_location')
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
        'on_change_with_warehouse_storage')
    warehouse_input = fields.Function(fields.Many2One('stock.location',
            'Warehouse Input', on_change_with=['warehouse']),
        'on_change_with_warehouse_input')
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
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        readonly=True)
    code = fields.Char("Code", size=None, select=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ('received', 'Received'),
        ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'delete_cancel': ('Customer Return Shipment "%s" must be '
                    'cancelled before deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'received'),
                ('received', 'done'),
                ('received', 'draf'),
                ('draft', 'cancel'),
                ('received', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
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

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_out_return'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, cls._table)

        table = TableHandler(cursor, cls, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentOutReturn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, Move._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON \'%s,\' || shipment.id = move.shipment '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (cls._table, Move._table, cls.__name__))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def on_change_customer(self):
        if not self.customer:
            return {'delivery_address': None}
        address = self.customer.address_get(type='delivery')
        return {
            'delivery_address': address.id,
            }

    def on_change_with_customer_location(self, name=None):
        if self.customer:
            return self.customer.customer_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    def on_change_with_warehouse_storage(self, name=None):
        if self.warehouse:
            return self.warehouse.storage_location.id

    @classmethod
    def default_warehouse_input(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_input()

    def on_change_with_warehouse_input(self, name=None):
        if self.warehouse:
            return self.warehouse.input_location.id

    def get_incoming_moves(self, name):
        moves = []
        for move in self.moves:
            if move.to_location.id == self.warehouse.input_location.id:
                moves.append(move.id)
        return moves

    @classmethod
    def set_incoming_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    def get_inventory_moves(self, name):
        moves = []
        for move in self.moves:
            if move.from_location.id == self.warehouse.input_location.id:
                moves.append(move.id)
        return moves

    @classmethod
    def set_inventory_moves(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'moves': value,
                })

    def _get_move_planned_date(self):
        '''
        Return the planned date for incoming moves and inventory moves
        '''
        return self.planned_date, self.planned_date

    @classmethod
    def _set_move_planned_date(cls, shipments):
        '''
        Set planned date of moves for the shipments
        '''
        Move = Pool().get('stock.move')
        for shipment in shipments:
            dates = shipment._get_move_planned_date()
            incoming_date, inventory_date = dates
            Move.write([x for x in shipment.incoming_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != incoming_date)], {
                    'planned_date': incoming_date,
                    })
            Move.write([x for x in shipment.inventory_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != inventory_date)], {
                    'planned_date': inventory_date,
                    })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(
                    config.shipment_out_return_sequence.id)
        shipments = super(ShipmentOutReturn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, shipments, values):
        super(ShipmentOutReturn, cls).write(shipments, values)
        cls._set_move_planned_date(shipments)

    @classmethod
    def copy(cls, shipments, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['inventory_moves'] = None
        default['incoming_moves'] = None
        return super(ShipmentOutReturn, cls).copy(shipments, default=default)

    @classmethod
    def delete(cls, shipments):
        Move = Pool().get('stock.move')
        # Cance before delete
        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', shipment.rec_name)
        Move.delete([m for s in shipments for m in s.moves])
        super(ShipmentOutReturn, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments for m in s.incoming_moves])
        Move.delete([m for s in shipments for m in s.inventory_moves
                if m.state in ('draft', 'cancel')])

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        Move = Pool().get('stock.move')
        Move.do([m for s in shipments for m in s.incoming_moves])
        cls.create_inventory_moves(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for s in shipments for m in s.inventory_moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments
                for m in s.incoming_moves + s.inventory_moves])

    @staticmethod
    def _get_inventory_moves(incoming_move):
        pool = Pool()
        Move = pool.get('stock.move')
        if incoming_move.quantity <= 0.0:
            return
        move = Move()
        move.product = incoming_move.product
        move.uom = incoming_move.uom
        move.quantity = incoming_move.quantity
        move.from_location = incoming_move.to_location
        move.to_location = incoming_move.shipment.warehouse.storage_location
        move.state = Move.default_state()
        # Product will be considered in stock only when the inventory
        # move will be made:
        move.planned_date = None
        move.company = incoming_move.company
        return move

    @classmethod
    def create_inventory_moves(cls, shipments):
        for shipment in shipments:
            # Use moves instead of inventory_moves because save reset before
            # adding new records and as set_inventory_moves is just a proxy to
            # moves, it will reset also the incoming_moves
            moves = list(shipment.moves)
            for incoming_move in shipment.incoming_moves:
                move = cls._get_inventory_moves(incoming_move)
                if move:
                    moves.append(move)
            shipment.moves = moves
            shipment.save()


class AssignShipmentOutAssignFailed(ModelView):
    'Assign Shipment Out'
    __name__ = 'stock.shipment.out.assign.failed'
    inventory_moves = fields.Many2Many('stock.move', None, None,
        'Inventory Moves', readonly=True)

    @staticmethod
    def default_inventory_moves():
        ShipmentOut = Pool().get('stock.shipment.out')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = ShipmentOut(shipment_id)
        return [x.id for x in shipment.inventory_moves if x.state == 'draft']


class AssignShipmentOut(Wizard):
    'Assign Shipment Out'
    __name__ = 'stock.shipment.out.assign'
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

    def transition_start(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')

        if Shipment.assign_try([Shipment(Transaction().context['active_id'])]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self):
        Shipment = Pool().get('stock.shipment.out')

        Shipment.assign_force([Shipment(Transaction().context['active_id'])])
        return 'end'


class ShipmentInternal(Workflow, ModelSQL, ModelView):
    "Internal Shipment"
    __name__ = 'stock.shipment.internal'
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
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
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

    @classmethod
    def __setup__(cls):
        super(ShipmentInternal, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'delete_cancel': ('Internal Shipment "%s" must be cancelled '
                    'before deletion.'),
                })
        cls._transitions |= set((
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
        cls._buttons.update({
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
                'assign_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'readonly': ~Eval('groups', []).contains(
                        Id('stock', 'group_stock')),
                    },
                'assign_try': {},
                'assign_force': {},
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_internal'
        if TableHandler.table_exist(cursor, old_table):
            TableHandler.table_rename(cursor, old_table, cls._table)
        table = TableHandler(cursor, cls, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        super(ShipmentInternal, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(cursor, Move._table)):
            cursor.execute('SELECT shipment.id, MAX(move.company) '
                'FROM "%s" AS shipment '
                'INNER JOIN "%s" AS move '
                'ON \'%s,\' || shipment.id = move.shipment '
                'GROUP BY shipment.id '
                'ORDER BY MAX(move.company)'
                % (cls._table, Move._table, cls.__name__))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for i in range(0, len(shipment_ids), cursor.IN_MAX):
                    sub_ids = shipment_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET company = %s WHERE ' + red_sql,
                        [company_id] + red_ids)
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(
                    config.shipment_internal_sequence.id)
        return super(ShipmentInternal, cls).create(vlist)

    @classmethod
    def delete(cls, shipments):
        Move = Pool().get('stock.move')
        # Cancel before delete
        cls.cancel(shipments)
        for shipment in shipments:
            if shipment.state != 'cancel':
                cls.raise_user_error('delete_cancel', shipment.rec_name)
        Move.delete([m for s in shipments for m in s.moves])
        super(ShipmentInternal, cls).delete(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments for m in s.moves])

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments):
        Move = Pool().get('stock.move')
        # First reset state to draft to allow update from and to location
        Move.draft([m for s in shipments for m in s.moves])
        for shipment in shipments:
            Move.write([m for m in shipment.moves
                    if m.state != 'done'], {
                    'from_location': shipment.from_location.id,
                    'to_location': shipment.to_location.id,
                    'planned_date': shipment.planned_date,
                    })

    @classmethod
    @Workflow.transition('assigned')
    def assign(cls, shipments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Move.do([m for s in shipments for m in s.moves])
        cls.write(shipments, {
                'effective_date': Date.today(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, shipments):
        Move = Pool().get('stock.move')
        Move.cancel([m for s in shipments for m in s.moves])

    @classmethod
    @ModelView.button_action('stock.wizard_shipment_internal_assign')
    def assign_wizard(cls, shipments):
        pass

    @classmethod
    @ModelView.button
    def assign_try(cls, shipments):
        Move = Pool().get('stock.move')
        if Move.assign_try([m for s in shipments
                    for m in s.moves]):
            cls.assign(shipments)
            return True
        else:
            return False

    @classmethod
    @ModelView.button
    def assign_force(cls, shipments):
        Move = Pool().get('stock.move')
        Move.assign([m for s in shipments for m in s.moves])
        cls.assign(shipments)


class Address:
    __name__ = 'party.address'
    delivery = fields.Boolean('Delivery')


class AssignShipmentInternalAssignFailed(ModelView):
    'Assign Shipment Internal'
    __name__ = 'stock.shipment.internal.assign.failed'
    moves = fields.Many2Many('stock.move', None, None, 'Moves',
        readonly=True)

    @staticmethod
    def default_moves():
        ShipmentInternal = Pool().get('stock.shipment.internal')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = ShipmentInternal(shipment_id)
        return [x.id for x in shipment.moves if x.state == 'draft']


class AssignShipmentInternal(Wizard):
    'Assign Shipment Internal'
    __name__ = 'stock.shipment.internal.assign'
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

    def transition_start(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.internal')

        if Shipment.assign_try([Shipment(Transaction().context['active_id'])]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self):
        Shipment = Pool().get('stock.shipment.internal')

        Shipment.assign_force([Shipment(Transaction().context['active_id'])])
        return 'end'


class AssignShipmentInReturnAssignFailed(ModelView):
    'Assign Supplier Return Shipment'
    __name__ = 'stock.shipment.in.return.assign.failed'
    moves = fields.Many2Many('stock.move', None, None, 'Moves',
            readonly=True)

    @staticmethod
    def default_moves():
        ShipmentInternal = Pool().get('stock.shipment.in.return')
        shipment_id = Transaction().context.get('active_id')
        if not shipment_id:
            return []
        shipment = ShipmentInternal(shipment_id)
        return [x.id for x in shipment.moves if x.state == 'draft']


class AssignShipmentInReturn(Wizard):
    'Assign Supplier Return Shipment'
    __name__ = 'stock.shipment.in.return.assign'
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

    def transition_start(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.in.return')

        if Shipment.assign_try([Shipment(Transaction().context['active_id'])]):
            return 'end'
        else:
            return 'failed'

    def transition_force(self):
        Shipment = Pool().get('stock.shipment.in.return')

        Shipment.assign_force([Shipment(Transaction().context['active_id'])])
        return 'end'


class CreateShipmentOutReturn(Wizard):
    'Create Customer Return Shipment'
    __name__ = 'stock.shipment.out.return.create'
    start = StateAction('stock.act_shipment_out_return_form')

    @classmethod
    def __setup__(cls):
        super(CreateShipmentOutReturn, cls).__setup__()
        cls._error_messages.update({
                'shipment_done_title': 'You can not create return shipment',
                'shipment_done_msg': ('The shipment with code "%s" is not yet '
                    'sent.'),
                })

    def do_start(self, action):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        shipment_ids = Transaction().context['active_ids']
        shipment_outs = ShipmentOut.browse(shipment_ids)

        to_create = []
        for shipment_out in shipment_outs:
            if shipment_out.state != 'done':
                self.raise_user_error('shipment_done_title',
                        error_description='shipment_done_msg',
                        error_description_args=shipment_out.code)

            incoming_moves = []
            moves_to_create = []
            for move in shipment_out.outgoing_moves:
                moves_to_create.append({
                        'product': move.product.id,
                        'quantity': move.quantity,
                        'uom': move.uom.id,
                        'from_location': move.to_location.id,
                        'to_location': (
                            shipment_out.warehouse.input_location.id),
                        'company': move.company.id,
                        })
            if moves_to_create:
                incoming_moves.append(('create', moves_to_create))
            to_create.append({
                    'customer': shipment_out.customer.id,
                    'delivery_address': shipment_out.delivery_address.id,
                    'warehouse': shipment_out.warehouse.id,
                    'incoming_moves': incoming_moves,
                    })
        shipment_out_returns = ShipmentOutReturn.create(to_create)

        data = {'res_id': [x.id for x in shipment_out_returns]}
        if len(shipment_out_returns) == 1:
            action['views'].reverse()
        return action, data

    def transition_start(self):
        return 'end'


class DeliveryNote(CompanyReport):
    'Delivery Note'
    __name__ = 'stock.shipment.out.delivery_note'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        localcontext['product_name'] = lambda product_id, language: \
            cls.product_name(product_id, language)
        return super(DeliveryNote, cls).parse(report, objects, data,
                localcontext)

    @classmethod
    def product_name(cls, product_id, language):
        Product = Pool().get('product.product')
        with Transaction().set_context(language=language):
            return Product(product_id).rec_name


class PickingList(CompanyReport):
    'Picking List'
    __name__ = 'stock.shipment.out.picking_list'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        compare_context = cls.get_compare_context(report, objects, data)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x, y: cmp(cls.get_compare_key(x, compare_context),
                    cls.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(PickingList, cls).parse(report, objects, data,
            localcontext)

    @staticmethod
    def get_compare_context(report, objects, data):
        Location = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_locations = Location.search(list(from_location_ids))
        to_locations = Location.search(list(to_location_ids))

        return {
            'from_location_ids': [l.id for l in from_locations],
            'to_location_ids': [l.id for l in to_locations],
            }

    @staticmethod
    def get_compare_key(move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]


class SupplierRestockingList(CompanyReport):
    'Supplier Restocking List'
    __name__ = 'stock.shipment.in.restocking_list'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        compare_context = cls.get_compare_context(report, objects, data)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x, y: cmp(cls.get_compare_key(x, compare_context),
                    cls.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(SupplierRestockingList, cls).parse(report, objects,
                data, localcontext)

    @staticmethod
    def get_compare_context(report, objects, data):
        Location = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_locations = Location.search(list(from_location_ids))
        to_locations = Location.search(list(to_location_ids))

        return {
            'from_location_ids': [l.id for l in from_locations],
            'to_location_ids': [l.id for l in to_locations],
            }

    @staticmethod
    def get_compare_key(move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]


class CustomerReturnRestockingList(CompanyReport):
    'Customer Return Restocking List'
    __name__ = 'stock.shipment.out.return.restocking_list'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        compare_context = cls.get_compare_context(report, objects, data)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.inventory_moves,
                lambda x, y: cmp(cls.get_compare_key(x, compare_context),
                    cls.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(CustomerReturnRestockingList, cls).parse(report,
                objects, data, localcontext)

    @staticmethod
    def get_compare_context(report, objects, data):
        Location = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.inventory_moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_locations = Location.search(list(from_location_ids))
        to_locations = Location.search(list(to_location_ids))

        return {
            'from_location_ids': [l.id for l in from_locations],
            'to_location_ids': [l.id for l in to_locations],
            }

    @staticmethod
    def get_compare_key(move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]


class InteralShipmentReport(CompanyReport):
    'Interal Shipment Report'
    __name__ = 'stock.shipment.internal.report'

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        compare_context = cls.get_compare_context(report, objects, data)

        sorted_moves = {}
        for shipment in objects:
            sorted_moves[shipment.id] = sorted(
                shipment.moves,
                lambda x, y: cmp(cls.get_compare_key(x, compare_context),
                    cls.get_compare_key(y, compare_context))
                )

        localcontext['moves'] = sorted_moves

        return super(InteralShipmentReport, cls).parse(report, objects,
            data, localcontext)

    @staticmethod
    def get_compare_context(report, objects, data):
        Location = Pool().get('stock.location')
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in obj.moves:
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        from_locations = Location.search(list(from_location_ids))
        to_locations = Location.search(list(to_location_ids))

        return {
            'from_location_ids': [l.id for l in from_locations],
            'to_location_ids': [l.id for l in to_locations],
            }

    @staticmethod
    def get_compare_key(move, compare_context):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]
