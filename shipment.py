# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import operator
import itertools
import functools
import datetime
from sql import Table
from sql.functions import Overlay, Position
from sql.aggregate import Max
from sql.operators import Concat

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond import backend
from trytond.pyson import Eval, If, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids, grouped_slice

__all__ = ['ShipmentIn', 'ShipmentInReturn',
    'ShipmentOut', 'ShipmentOutReturn',
    'AssignShipmentOutAssignFailed', 'AssignShipmentOut',
    'ShipmentInternal',
    'Address',
    'AssignShipmentInternalAssignFailed', 'AssignShipmentInternal',
    'AssignShipmentInReturnAssignFailed', 'AssignShipmentInReturn',
    'DeliveryNote', 'PickingList',
    'SupplierRestockingList', 'CustomerReturnRestockingList',
    'InteralShipmentReport']

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class ShipmentIn(Workflow, ModelSQL, ModelView):
    "Supplier Shipment"
    __name__ = 'stock.shipment.in'
    _rec_name = 'number'
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date', states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    supplier = fields.Many2One('party.party', 'Supplier',
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('incoming_moves', [0]))
                & Eval('supplier')),
            }, required=True,
        depends=['state', 'supplier'])
    supplier_location = fields.Function(fields.Many2One('stock.location',
            'Supplier Location'),
        'on_change_with_supplier_location')
    contact_address = fields.Many2One('party.address', 'Contact Address',
        states={
            'readonly': Eval('state') != 'draft',
            }, domain=[('party', '=', Eval('supplier'))],
        depends=['state', 'supplier'])
    warehouse = fields.Many2One('stock.location', "Warehouse",
        required=True, domain=[('type', '=', 'warehouse')],
        states={
            'readonly': (Eval('state').in_(['cancel', 'done'])
                | Eval('incoming_moves', [0])),
            }, depends=['state'])
    warehouse_input = fields.Function(fields.Many2One('stock.location',
            'Warehouse Input'),
        'on_change_with_warehouse_input')
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage'),
        'on_change_with_warehouse_storage')
    incoming_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
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
    inventory_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
            'Inventory Moves',
            domain=[
                ('from_location', '=', Eval('warehouse_input')),
                ('to_location', 'child_of', [Eval('warehouse_storage', -1)],
                    'parent'),
                ('company', '=', Eval('company')),
                ],
            states={
                'readonly': Eval('state').in_(['draft', 'done', 'cancel']),
                },
            depends=['state', 'warehouse', 'warehouse_input',
                'warehouse_storage', 'company']),
        'get_inventory_moves', setter='set_inventory_moves')
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        domain=[('company', '=', Eval('company'))], readonly=True,
        depends=['company'])
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
    number = fields.Char('Numer', size=None, select=True, readonly=True)
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        model_data = Table('ir_model_data')
        model = Table('ir_model')
        model_field = Table('ir_model_field')
        sql_table = cls.__table__()

        # Migration from 1.2: packing renamed into shipment
        cursor.execute(*model_data.update(
                columns=[model_data.fs_id],
                values=[Overlay(model_data.fs_id, 'shipment',
                        Position('packing', model_data.fs_id),
                        len('packing'))],
                where=model_data.fs_id.like('%packing%')
                & (model_data.module == module_name)))
        cursor.execute(*model.update(
                columns=[model.model],
                values=[Overlay(model.model, 'shipment',
                        Position('packing', model.model),
                        len('packing'))],
                where=model.model.like('%packing%')
                & (model.module == module_name)))
        cursor.execute(*model_field.update(
                columns=[model_field.relation],
                values=[Overlay(model_field.relation, 'shipment',
                        Position('packing', model_field.relation),
                        len('packing'))],
                where=model_field.relation.like('%packing%')
                & (model_field.module == module_name)))
        cursor.execute(*model_field.update(
                columns=[model_field.name],
                values=[Overlay(model_field.name, 'shipment',
                        Position('packing', model_field.name),
                        len('packing'))],
                where=model_field.name.like('%packing%')
                & (model_field.module == module_name)))

        old_table = 'stock_packing_in'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)
        table = TableHandler(cls, module_name)
        for field in ('create_uid', 'write_uid', 'contact_address',
                'warehouse', 'supplier'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        # Migration from 3.8: rename code into number
        if table.column_exist('code'):
            table.column_rename('code', 'number')

        super(ShipmentIn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(Move._table)):
            move = Move.__table__()
            cursor.execute(*sql_table.join(move,
                    condition=(Concat(cls.__name__ + ',', sql_table.id)
                        == move.shipment)
                    ).select(sql_table.id, Max(move.company),
                    group_by=sql_table.id,
                    order_by=Max(move.company)))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for sub_ids in grouped_slice(shipment_ids):
                    red_sql = reduce_ids(sql_table.id, sub_ids)
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.company],
                            values=[company_id],
                            where=red_sql))
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_planned_date():
        return Pool().get('ir.date').today()

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

    @fields.depends('supplier')
    def on_change_supplier(self):
        self.contact_address = None
        if self.supplier:
            self.contact_address = self.supplier.address_get()

    @fields.depends('supplier')
    def on_change_with_supplier_location(self, name=None):
        if self.supplier:
            return self.supplier.supplier_location.id

    @classmethod
    def default_warehouse_input(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_input()

    @fields.depends('warehouse')
    def on_change_with_warehouse_input(self, name=None):
        if self.warehouse:
            return self.warehouse.input_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    @fields.depends('warehouse')
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
            # Update planned_date only for later to not be too optimistic if
            # the shipment is not directly received.
            Move.write([m for m in shipment.incoming_moves
                    if (m.state not in ('assigned', 'done', 'cancel')
                        and ((m.planned_date or datetime.date.max)
                            < (incoming_date or datetime.date.max)))], {
                    'planned_date': incoming_date,
                    })
            Move.write([m for m in shipment.inventory_moves
                    if (m.state not in ('assigned', 'done', 'cancel')
                        and ((m.planned_date or datetime.date.max)
                            < (inventory_date or datetime.date.max)))], {
                    'planned_date': inventory_date,
                    })

    def get_origins(self, name):
        return ', '.join(set(itertools.ifilter(None,
                    (m.origin_name for m in self.moves))))

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(config.shipment_in_sequence)
        shipments = super(ShipmentIn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        super(ShipmentIn, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

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
        Move.draft([m for s in shipments for m in s.incoming_moves
                if m.state != 'staging'])
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
        cls.write([s for s in shipments if not s.effective_date], {
                'effective_date': Date.today(),
                })


class ShipmentInReturn(Workflow, ModelSQL, ModelView):
    "Supplier Return Shipment"
    __name__ = 'stock.shipment.in.return'
    _rec_name = 'number'
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    number = fields.Char('Number', size=None, select=True, readonly=True)
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    supplier = fields.Many2One('party.party', 'Supplier',
        states={
            'readonly': (((Eval('state') != 'draft')
                    | Eval('moves', [0]))
                    & Eval('supplier', 0)),
            }, required=True,
        depends=['state', 'supplier'])
    delivery_address = fields.Many2One('party.address', 'Delivery Address',
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('party', '=', Eval('supplier'))
            ],
        depends=['state', 'supplier'])
    from_location = fields.Many2One('stock.location', "From Location",
        required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('moves', [0]),
            }, domain=[('type', 'in', ['storage', 'view'])],
        depends=['state'])
    to_location = fields.Many2One('stock.location', "To Location",
        required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('moves', [0]),
            }, domain=[('type', '=', 'supplier')],
        depends=['state'])
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        states={
            'readonly': (((Eval('state') != 'draft') | ~Eval('from_location'))
                & Eval('to_location')),
            },
        domain=[
            ('from_location', '=', Eval('from_location')),
            ('to_location', '=', Eval('to_location')),
            ('company', '=', Eval('company')),
            ],
        depends=['state', 'from_location', 'to_location', 'company'])
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_in_return'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)
        table = TableHandler(cls, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        # Migration from 3.8: rename code into number
        if table.column_exist('code'):
            table.column_rename('code', 'number')

        super(ShipmentInReturn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(Move._table)):
            move = Move.__table__()
            cursor.execute(*sql_table.join(move,
                    condition=(Concat(cls.__name__ + ',', sql_table.id)
                        == move.shipment)
                    ).select(sql_table.id, Max(move.company),
                    group_by=sql_table.id,
                    order_by=Max(move.company)))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for sub_ids in grouped_slice(shipment_ids):
                    red_sql = reduce_ids(sql_table.id, sub_ids)
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.company],
                            values=[company_id],
                            where=red_sql))
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('supplier')
    def on_change_supplier(self):
        if self.supplier:
            self.delivery_address = self.supplier.address_get('delivery')
            self.to_location = self.supplier.supplier_location

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

    def get_origins(self, name):
        return ', '.join(set(itertools.ifilter(None,
                    (m.origin_name for m in self.moves))))

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.shipment_in_return_sequence.id)
        shipments = super(ShipmentInReturn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        super(ShipmentInReturn, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

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
        Move.draft([m for s in shipments for m in s.moves
                if m.state != 'staging'])

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
        cls.write([s for s in shipments if not s.effective_date], {
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
        Move = pool.get('stock.move')
        if Move.assign_try([m for s in shipments for m in s.moves],
                with_childs=False):
            cls.assign(shipments)
            return True
        else:
            return False

    @classmethod
    @ModelView.button
    def assign_force(cls, shipments):
        cls.assign(shipments)


class ShipmentOut(Workflow, ModelSQL, ModelView):
    "Customer Shipment"
    __name__ = 'stock.shipment.out'
    _rec_name = 'number'
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('outgoing_moves', [0])),
            },
        depends=['state'])
    customer_location = fields.Function(fields.Many2One('stock.location',
            'Customer Location'), 'on_change_with_customer_location')
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('outgoing_moves', [0])),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state'])
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage'), 'on_change_with_warehouse_storage')
    warehouse_output = fields.Function(fields.Many2One('stock.location',
            'Warehouse Output'), 'on_change_with_warehouse_output')
    outgoing_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
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
    inventory_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
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
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
    number = fields.Char('Number', size=None, select=True, readonly=True)
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_out'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)

        table = TableHandler(cls, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        # Migration from 3.8: rename code into number
        if table.column_exist('code'):
            table.column_rename('code', 'number')

        super(ShipmentOut, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(Move._table)):
            move = Move.__table__()
            cursor.execute(*sql_table.join(move,
                    condition=(Concat(cls.__name__ + ',', sql_table.id)
                        == move.shipment)
                    ).select(sql_table.id, Max(move.company),
                    group_by=sql_table.id,
                    order_by=Max(move.company)))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for sub_ids in grouped_slice(shipment_ids):
                    red_sql = reduce_ids(sql_table.id, sub_ids)
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.company],
                            values=[company_id],
                            where=red_sql))
            table.not_null_action('company', action='add')

        # Migration from 1.0 customer_location is no more used
        table = TableHandler(cls, module_name)
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

    @fields.depends('customer')
    def on_change_customer(self):
        self.delivery_address = None
        if self.customer:
            self.delivery_address = self.customer.address_get(type='delivery')

    @fields.depends('customer')
    def on_change_with_customer_location(self, name=None):
        if self.customer:
            return self.customer.customer_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    @fields.depends('warehouse')
    def on_change_with_warehouse_storage(self, name=None):
        if self.warehouse:
            return self.warehouse.storage_location.id

    @classmethod
    def default_warehouse_output(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_output()

    @fields.depends('warehouse')
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

    def get_origins(self, name):
        return ', '.join(set(itertools.ifilter(None,
                    (m.origin_name for m in self.moves))))

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments
                for m in s.inventory_moves + s.outgoing_moves
                if m.state != 'staging'])

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
                to_create.append(shipment._get_inventory_move(move))
        if to_create:
            Move.save(to_create)

    def _get_inventory_move(self, move):
        'Return inventory move for the outgoing move'
        pool = Pool()
        Move = pool.get('stock.move')
        wrh = move.shipment.warehouse
        return Move(
            from_location=wrh.picking_location or wrh.storage_location,
            to_location=move.from_location,
            product=move.product,
            uom=move.uom,
            quantity=move.quantity,
            shipment=self,
            planned_date=move.planned_date,
            company=move.company,
            currency=move.currency,
            unit_price=move.unit_price,
            state='staging' if move.state == 'staging' else 'draft',
            )

    @classmethod
    @Workflow.transition('assigned')
    def assign(cls, shipments):
        cls._sync_inventory_to_outgoing(shipments, create=True, write=False)

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Move.do([m for s in shipments for m in s.inventory_moves])
        cls._sync_inventory_to_outgoing(shipments)
        Move.assign([m for s in shipments for m in s.outgoing_moves])

    def _get_outgoing_move(self, move):
        'Return outgoing move for the inventory move'
        pool = Pool()
        Move = pool.get('stock.move')
        return Move(
            from_location=move.to_location,
            to_location=self.customer.customer_location,
            product=move.product,
            uom=move.uom,
            quantity=move.quantity,
            shipment=self,
            planned_date=self.planned_date,
            company=move.company,
            currency=move.company.currency,
            unit_price=move.unit_price,
            )

    @classmethod
    def _sync_inventory_to_outgoing(cls, shipments, create=True, write=True):
        'Synchronise outgoing moves with inventory moves'
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
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

                if not out_quantity:
                    continue
                unit_price = Uom.compute_price(move.product.default_uom,
                        move.product.list_price, move.uom)
                to_create.append(shipment._get_outgoing_move(move))
                to_create[-1].quantity = out_quantity
                to_create[-1].unit_price = unit_price
            if create and to_create:
                Move.save(to_create)

            # Re-read the shipment and remove exceeding quantities
            for move in shipment.outgoing_moves:
                if move.state == 'cancel':
                    continue
                if outgoing_qty.get(move.product.id, 0.0) > 0.0:
                    exc_qty = Uom.compute_qty(move.product.default_uom,
                            outgoing_qty[move.product.id], move.uom)
                    removed_qty = Uom.compute_qty(move.uom,
                        min(exc_qty, move.quantity), move.product.default_uom,
                        round=False)
                    if write:
                        Move.write([move], {
                                'quantity': max(0.0, move.quantity - exc_qty),
                                })
                    outgoing_qty[move.product.id] -= removed_qty

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        Move.do([m for s in shipments for m in s.outgoing_moves])
        cls.write([s for s in shipments if not s.effective_date], {
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
        to_write = []
        for shipment in shipments:
            outgoing_date, inventory_date = shipment._move_planned_date
            out_moves_to_write = [x for x in shipment.outgoing_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != outgoing_date)]
            if out_moves_to_write:
                to_write.extend((out_moves_to_write, {
                        'planned_date': outgoing_date,
                        }))

            inv_moves_to_write = [x for x in shipment.inventory_moves
                    if (x.state not in ('assigned', 'done', 'cancel')
                        and x.planned_date != inventory_date)]
            if inv_moves_to_write:
                to_write.extend((inv_moves_to_write, {
                        'planned_date': inventory_date,
                        }))
        if to_write:
            Move.write(*to_write)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.shipment_out_sequence.id)
        shipments = super(ShipmentOut, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        super(ShipmentOut, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

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
    _rec_name = 'number'
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    customer = fields.Many2One('party.party', 'Customer', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('incoming_moves', [0])),
            },
        depends=['state'])
    customer_location = fields.Function(fields.Many2One('stock.location',
            'Customer Location'), 'on_change_with_customer_location')
    delivery_address = fields.Many2One('party.address',
        'Delivery Address', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, domain=[('party', '=', Eval('customer'))],
        depends=['state', 'customer'])
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    warehouse = fields.Many2One('stock.location', "Warehouse", required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | Eval('incoming_moves', [0])),
            }, domain=[('type', '=', 'warehouse')],
        depends=['state'])
    warehouse_storage = fields.Function(fields.Many2One('stock.location',
            'Warehouse Storage'), 'on_change_with_warehouse_storage')
    warehouse_input = fields.Function(fields.Many2One('stock.location',
            'Warehouse Input'), 'on_change_with_warehouse_input')
    incoming_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
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
    inventory_moves = fields.Function(fields.One2Many('stock.move', 'shipment',
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
    origins = fields.Function(fields.Char('Origins'), 'get_origins')
    number = fields.Char('Number', size=None, select=True, readonly=True)
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
                ('received', 'draft'),
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_out_return'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)

        table = TableHandler(cls, module_name)
        for field in ('create_uid', 'write_uid', 'delivery_address',
                'warehouse', 'customer'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        # Migration from 3.8: rename code into number
        if table.column_exist('code'):
            table.column_rename('code', 'number')

        super(ShipmentOutReturn, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(Move._table)):
            move = Move.__table__()
            cursor.execute(*sql_table.join(move,
                    condition=(Concat(cls.__name__ + ',', sql_table.id)
                        == move.shipment)
                    ).select(sql_table.id, Max(move.company),
                    group_by=sql_table.id,
                    order_by=Max(move.company)))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for sub_ids in grouped_slice(shipment_ids):
                    red_sql = reduce_ids(sql_table.id, sub_ids)
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.company],
                            values=[company_id],
                            where=red_sql))
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cls, module_name)
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

    @fields.depends('customer')
    def on_change_customer(self):
        self.delivery_address = None
        if self.customer:
            self.delivery_address = self.customer.address_get(type='delivery')

    @fields.depends('customer')
    def on_change_with_customer_location(self, name=None):
        if self.customer:
            return self.customer.customer_location.id

    @classmethod
    def default_warehouse_storage(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_storage()

    @fields.depends('warehouse')
    def on_change_with_warehouse_storage(self, name=None):
        if self.warehouse:
            return self.warehouse.storage_location.id

    @classmethod
    def default_warehouse_input(cls):
        warehouse = cls.default_warehouse()
        if warehouse:
            return cls(warehouse=warehouse).on_change_with_warehouse_input()

    @fields.depends('warehouse')
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

    def get_origins(self, name):
        return ', '.join(set(itertools.ifilter(None,
                    (m.origin_name for m in self.moves))))

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [x.copy() for x in vlist]
        config = Config(1)
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                        config.shipment_out_return_sequence.id)
        shipments = super(ShipmentOutReturn, cls).create(vlist)
        cls._set_move_planned_date(shipments)
        return shipments

    @classmethod
    def write(cls, *args):
        super(ShipmentOutReturn, cls).write(*args)
        cls._set_move_planned_date(sum(args[::2], []))

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
        Move.draft([m for s in shipments for m in s.incoming_moves
                if m.state != 'staging'])
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
        cls.write([s for s in shipments if not s.effective_date], {
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
            Button('OK', 'end', 'tryton-ok', True),
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
    _rec_name = 'number'
    effective_date = fields.Date('Effective Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    planned_date = fields.Date('Planned Date',
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'])
    number = fields.Char('Number', size=None, select=True, readonly=True)
    reference = fields.Char("Reference", size=None, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])
    from_location = fields.Many2One('stock.location', "From Location",
        required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('moves', [0]),
            },
        domain=[
            ('type', 'in', ['view', 'storage', 'lost_found']),
            ], depends=['state'])
    to_location = fields.Many2One('stock.location', "To Location",
        required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('moves', [0]),
            }, domain=[
            ('type', 'in', ['view', 'storage', 'lost_found']),
            ], depends=['state'])
    moves = fields.One2Many('stock.move', 'shipment', 'Moves',
        states={
            'readonly': (Eval('state').in_(['cancel', 'assigned', 'done'])
                | ~Eval('from_location') | ~Eval('to_location')),
            },
        domain=[
            If(Eval('state') == 'draft', [
                    ('from_location', '=', Eval('from_location')),
                    ('to_location', '=', Eval('to_location')),
                    ], [
                    ('from_location', 'child_of', [Eval('from_location', -1)],
                        'parent'),
                    ('to_location', 'child_of', [Eval('to_location', -1)],
                        'parent'),
                    ]),
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
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        # Migration from 1.2: packing renamed into shipment
        old_table = 'stock_packing_internal'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)
        table = TableHandler(cls, module_name)
        for field in ('create_uid', 'write_uid', 'from_location',
                'to_location'):
            table.drop_fk(field, table=old_table)
        for field in ('code', 'reference'):
            table.index_action(field, action='remove', table=old_table)

        # Migration from 2.0:
        created_company = table.column_exist('company')

        # Migration from 3.8:
        if table.column_exist('code'):
            table.column_rename('code', 'number')

        super(ShipmentInternal, cls).__register__(module_name)

        # Migration from 2.0:
        Move = Pool().get('stock.move')
        if (not created_company
                and TableHandler.table_exist(Move._table)):
            move = Move.__table__()
            cursor.execute(*sql_table.join(move,
                    condition=(Concat(cls.__name__ + ',', sql_table.id)
                        == move.shipment)
                    ).select(sql_table.id, Max(move.company),
                    group_by=sql_table.id,
                    order_by=Max(move.company)))
            for company_id, values in itertools.groupby(cursor.fetchall(),
                    operator.itemgetter(1)):
                shipment_ids = [x[0] for x in values]
                for sub_ids in grouped_slice(shipment_ids):
                    red_sql = reduce_ids(sql_table.id, sub_ids)
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.company],
                            values=[company_id],
                            where=red_sql))
            table.not_null_action('company', action='add')

        # Add index on create_date
        table = TableHandler(cls, module_name)
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
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
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
        # First reset state to draft to allow update from and to location
        Move.draft([m for s in shipments for m in s.moves
                if m.state != 'staging'])
        for shipment in shipments:
            Move.write([m for m in shipment.moves
                    if m.state != 'done'], {
                    'from_location': shipment.from_location.id,
                    'to_location': shipment.to_location.id,
                    'planned_date': shipment.planned_date,
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments):
        Move = Pool().get('stock.move')
        Move.draft([m for s in shipments for m in s.moves])
        moves = []
        for shipment in shipments:
            for move in shipment.moves:
                if move.state != 'done':
                    move.planned_date = shipment.planned_date
                    moves.append(move)
        Move.save(moves)

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
        cls.write([s for s in shipments if not s.effective_date], {
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
        to_assign = [m for s in shipments for m in s.moves
            if m.from_location.type != 'lost_found']
        if not to_assign or Move.assign_try(to_assign):
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
    __metaclass__ = PoolMeta
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
            Button('OK', 'end', 'tryton-ok', True),
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
            Button('OK', 'end', 'tryton-ok', True),
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


class DeliveryNote(CompanyReport):
    'Delivery Note'
    __name__ = 'stock.shipment.out.delivery_note'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(DeliveryNote, cls).get_context(records, data)
        report_context['product_name'] = lambda product_id, language: \
            cls.product_name(product_id, language)
        return report_context

    @classmethod
    def product_name(cls, product_id, language):
        Product = Pool().get('product.product')
        with Transaction().set_context(language=language):
            return Product(product_id).rec_name


class ShipmentReport(CompanyReport):
    move_attribute = 'inventory_moves'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ShipmentReport, cls).get_context(records, data)

        compare_context = cls.get_compare_context(records, data)
        sorted_moves = {}
        for shipment in records:
            sorted_moves[shipment.id] = sorted(
                getattr(shipment, cls.move_attribute),
                key=functools.partial(cls.get_compare_key, compare_context))
        report_context['moves'] = sorted_moves

        return report_context

    @classmethod
    def get_compare_context(cls, objects, data):
        from_location_ids = set()
        to_location_ids = set()
        for obj in objects:
            for move in getattr(obj, cls.move_attribute):
                from_location_ids.add(move.from_location.id)
                to_location_ids.add(move.to_location.id)

        return {
            'from_location_ids': list(from_location_ids),
            'to_location_ids': list(to_location_ids),
            }

    @staticmethod
    def get_compare_key(compare_context, move):
        from_location_ids = compare_context['from_location_ids']
        to_location_ids = compare_context['to_location_ids']
        return [from_location_ids.index(move.from_location.id),
                to_location_ids.index(move.to_location.id)]


class PickingList(ShipmentReport):
    'Picking List'
    __name__ = 'stock.shipment.out.picking_list'


class SupplierRestockingList(ShipmentReport):
    'Supplier Restocking List'
    __name__ = 'stock.shipment.in.restocking_list'


class CustomerReturnRestockingList(ShipmentReport):
    'Customer Return Restocking List'
    __name__ = 'stock.shipment.out.return.restocking_list'


class InteralShipmentReport(ShipmentReport):
    'Interal Shipment Report'
    __name__ = 'stock.shipment.internal.report'
    move_attribute = 'moves'
