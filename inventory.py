# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.model import Workflow, Model, ModelView, ModelSQL, fields, Check
from trytond.pyson import Eval, Bool
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Inventory', 'InventoryLine']

STATES = {
    'readonly': Eval('state') != 'draft',
}
DEPENDS = ['state']
INVENTORY_STATES = [
    ('draft', 'Draft'),
    ('done', 'Done'),
    ('cancel', 'Canceled'),
    ]


class Inventory(Workflow, ModelSQL, ModelView):
    'Stock Inventory'
    __name__ = 'stock.inventory'
    _rec_name = 'number'
    number = fields.Char('Number', readonly=True)
    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        depends=['state'])
    date = fields.Date('Date', required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        depends=['state'])
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')], states=STATES, depends=DEPENDS)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Lines', states=STATES,
        depends=DEPENDS)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        depends=['state'])
    state = fields.Selection(
        INVENTORY_STATES, 'State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(Inventory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._error_messages.update({
                'delete_cancel': ('Inventory "%s" must be cancelled before '
                    'deletion.'),
                'unique_line': ('Line "%s" is not unique '
                    'on Inventory "%s".'),
                })
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancel'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state').in_(['done', 'cancel']),
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'complete_lines': {
                    'readonly': Eval('state') != 'draft',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(Inventory, cls).__register__(module_name)

        # Add index on create_date
        table = TableHandler(cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_lost_found(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.lost_found.domain)
        if len(locations) == 1:
            return locations[0].id

    @classmethod
    def delete(cls, inventories):
        # Cancel before delete
        cls.cancel(inventories)
        for inventory in inventories:
            if inventory.state != 'cancel':
                cls.raise_user_error('delete_cancel', inventory.rec_name)
        super(Inventory, cls).delete(inventories)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def confirm(cls, inventories):
        Move = Pool().get('stock.move')
        moves = []
        for inventory in inventories:
            keys = set()
            for line in inventory.lines:
                key = line.unique_key
                if key in keys:
                    cls.raise_user_error('unique_line',
                        (line.rec_name, inventory.rec_name))
                keys.add(key)
                move = line.get_move()
                if move:
                    moves.append(move)
        if moves:
            Move.save(moves)
            Move.do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, inventories):
        Line = Pool().get("stock.inventory.line")
        Line.cancel_move([l for i in inventories for l in i.lines])

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('stock.configuration')
        config = Configuration(1)
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.inventory_sequence.id)
        inventories = super(Inventory, cls).create(vlist)
        cls.complete_lines(inventories, fill=False)
        return inventories

    @classmethod
    def write(cls, inventories, values):
        super(Inventory, cls).write(inventories, values)
        cls.complete_lines(inventories, fill=False)

    @classmethod
    def copy(cls, inventories, default=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('stock.inventory.line')

        if default is None:
            default = {}
        default = default.copy()
        default['date'] = Date.today()
        default['lines'] = None
        default.setdefault('number')

        new_inventories = []
        for inventory in inventories:
            new_inventory, = super(Inventory, cls).copy([inventory],
                default=default)
            Line.copy(inventory.lines,
                default={
                    'inventory': new_inventory.id,
                    'moves': None,
                    })
            cls.complete_lines([new_inventory], fill=False)
            new_inventories.append(new_inventory)
        return new_inventories

    @staticmethod
    def grouping():
        return ('product',)

    @classmethod
    @ModelView.button
    def complete_lines(cls, inventories, fill=True):
        '''
        Complete or update the inventories
        '''
        pool = Pool()
        Line = pool.get('stock.inventory.line')
        Product = pool.get('product.product')

        grouping = cls.grouping()
        to_create, to_write = [], []
        for inventory in inventories:
            # Once done computation is wrong because include created moves
            if inventory.state == 'done':
                continue
            # Compute product quantities
            if fill:
                product_ids = None
            else:
                product_ids = [l.product.id for l in inventory.lines]
            with Transaction().set_context(stock_date_end=inventory.date):
                pbl = Product.products_by_location(
                    [inventory.location.id], product_ids=product_ids,
                    grouping=grouping)

            # Index some data
            product2type = {}
            product2consumable = {}
            for product in Product.browse([line[1] for line in pbl]):
                product2type[product.id] = product.type
                product2consumable[product.id] = product.consumable

            # Update existing lines
            for line in inventory.lines:
                if not (line.product.active and
                        line.product.type == 'goods'
                        and not line.product.consumable):
                    Line.delete([line])
                    continue

                key = (inventory.location.id,) + line.unique_key
                if key in pbl:
                    quantity = pbl.pop(key)
                else:
                    quantity = 0.0
                values = line.update_values4complete(quantity)
                if values:
                    to_write.extend(([line], values))

            if not fill:
                continue
            # Create lines if needed
            for key, quantity in pbl.iteritems():
                product_id = key[grouping.index('product') + 1]
                if (product2type[product_id] != 'goods'
                        or product2consumable[product_id]):
                    continue
                if not quantity:
                    continue

                values = Line.create_values4complete(inventory, quantity)
                for i, fname in enumerate(grouping, 1):
                    values[fname] = key[i]
                to_create.append(values)
        if to_create:
            Line.create(to_create)
        if to_write:
            Line.write(*to_write)


class InventoryLine(ModelSQL, ModelView):
    'Stock Inventory Line'
    __name__ = 'stock.inventory.line'
    _rec_name = 'product'
    _states = {
        'readonly': Eval('inventory_state') != 'draft',
        }
    _depends = ['inventory_state']

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ], states=_states, depends=_depends)
    uom = fields.Function(fields.Many2One('product.uom', 'UOM'), 'get_uom')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    expected_quantity = fields.Float('Expected Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), readonly=True,
            depends=['unit_digits'])
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        states=_states, depends=['unit_digits'] + _depends)
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Inventory', required=True,
        ondelete='CASCADE',
        states={
            'readonly': _states['readonly'] & Bool(Eval('inventory')),
            },
        depends=_depends)
    inventory_state = fields.Function(
        fields.Selection(INVENTORY_STATES, 'Inventory State'),
        'on_change_with_inventory_state')

    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_line_qty_pos', Check(t, t.quantity >= 0),
                'Line quantity must be positive.'),
            ]
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Move = pool.get('stock.move')
        sql_table = cls.__table__()
        move_table = Move.__table__()

        super(InventoryLine, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        # Migration from 2.8: Remove constraint inventory_product_uniq
        table.drop_constraint('inventory_product_uniq')

        # Migration from 3.0: use Move origin
        if table.column_exist('move'):
            cursor.execute(*sql_table.select(sql_table.id, sql_table.move,
                    where=sql_table.move != Null))
            for line_id, move_id in cursor.fetchall():
                cursor.execute(*move_table.update(
                        columns=[move_table.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=move_table.id == move_id))
            table.drop_column('move')

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_expected_quantity():
        return 0.

    @fields.depends('product')
    def on_change_product(self):
        self.unit_digits = 2
        if self.product:
            self.uom = self.product.default_uom
            self.unit_digits = self.product.default_uom.digits

    @fields.depends('inventory', '_parent_inventory.state')
    def on_change_with_inventory_state(self, name=None):
        if self.inventory:
            return self.inventory.state
        return 'draft'

    def get_rec_name(self, name):
        return self.product.rec_name

    def get_uom(self, name):
        return self.product.default_uom.id

    def get_unit_digits(self, name):
        return self.product.default_uom.digits

    @property
    def unique_key(self):
        key = []
        for fname in self.inventory.grouping():
            value = getattr(self, fname)
            if isinstance(value, Model):
                value = value.id
            key.append(value)
        return tuple(key)

    @classmethod
    def cancel_move(cls, lines):
        Move = Pool().get('stock.move')
        moves = [m for l in lines for m in l.moves if l.moves]
        Move.cancel(moves)
        Move.delete(moves)

    def get_move(self):
        '''
        Return Move instance for the inventory line
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')

        delta_qty = Uom.compute_qty(self.uom,
            self.expected_quantity - self.quantity,
            self.uom)
        if delta_qty == 0.0:
            return
        from_location = self.inventory.location
        to_location = self.inventory.lost_found
        if delta_qty < 0:
            (from_location, to_location, delta_qty) = \
                (to_location, from_location, -delta_qty)

        return Move(
            from_location=from_location,
            to_location=to_location,
            quantity=delta_qty,
            product=self.product,
            uom=self.uom,
            company=self.inventory.company,
            effective_date=self.inventory.date,
            origin=self,
            )

    def update_values4complete(self, quantity):
        '''
        Return update values to complete inventory
        '''
        values = {}
        # if nothing changed, no update
        if self.quantity == self.expected_quantity == quantity:
            return values
        values['expected_quantity'] = quantity
        # update also quantity field if not edited
        if self.quantity == self.expected_quantity:
            values['quantity'] = max(quantity, 0.0)
        return values

    @classmethod
    def create_values4complete(cls, inventory, quantity):
        '''
        Return create values to complete inventory
        '''
        return {
            'inventory': inventory.id,
            'expected_quantity': quantity,
            'quantity': max(quantity, 0.0),
        }
