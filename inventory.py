# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null

from trytond.i18n import gettext
from trytond.model import Check, Model, ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import (
    InventoryCountWarning, InventoryFutureWarning, InventoryValidationError)


class Inventory(Workflow, ModelSQL, ModelView):
    'Stock Inventory'
    __name__ = 'stock.inventory'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    number = fields.Char('Number', readonly=True,
        help="The main identifier for the inventory.")
    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        help="The location inventoried.")
    date = fields.Date('Date', required=True, states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        help="The date of the stock count.")
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Lines',
        states={
            'readonly': (_states['readonly'] | ~Eval('location')
                | ~Eval('date')),
            })
    empty_quantity = fields.Selection([
            (None, ""),
            ('keep', "Keep"),
            ('empty', "Empty"),
            ], "Empty Quantity", states=_states,
        help="How lines without a quantity are handled.")
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        help="The company the inventory is associated with.")
    state = fields.Selection([
            ('draft', "Draft"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, select=True, sort=False,
        help="The current state of the inventory.")

    del _states

    @classmethod
    def __setup__(cls):
        super(Inventory, cls).__setup__()
        cls.create_date.select = True
        cls._order.insert(0, ('date', 'DESC'))
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancelled'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state').in_(['done', 'cancelled']),
                    'depends': ['state'],
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled', 'done']),
                    'depends': ['state'],
                    },
                'complete_lines': {
                    'readonly': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'count': {
                    'readonly': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        super(Inventory, cls).__register__(module_name)

        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        # Migration from 5.4: remove lost_found
        table.not_null_action('lost_found', 'remove')

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

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
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    def delete(cls, inventories):
        # Cancel before delete
        cls.cancel(inventories)
        for inventory in inventories:
            if inventory.state != 'cancelled':
                raise AccessError(
                    gettext('stock.msg_inventory_delete_cancel',
                        inventory=inventory.rec_name))
        super(Inventory, cls).delete(inventories)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def confirm(cls, inventories):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')
        today_cache = {}

        def in_future(inventory):
            if inventory.company not in today_cache:
                with Transaction().set_context(company=inventory.company.id):
                    today_cache[inventory.company] = Date.today()
            today = today_cache[inventory.company]
            if inventory.date > today:
                return inventory
        future_inventories = sorted(filter(in_future, inventories))
        if future_inventories:
            names = ', '.join(i.rec_name for i in future_inventories[:5])
            if len(future_inventories) > 5:
                names + '...'
            warning_name = Warning.format('date_future', future_inventories)
            if Warning.check(warning_name):
                raise InventoryFutureWarning(warning_name,
                    gettext('stock.msg_inventory_date_in_the_future',
                        inventories=names))

        moves = []
        for inventory in inventories:
            keys = set()
            for line in inventory.lines:
                key = line.unique_key
                if key in keys:
                    raise InventoryValidationError(
                        gettext('stock.msg_inventory_line_unique',
                            line=line.rec_name,
                            inventory=inventory.rec_name))
                keys.add(key)
                move = line.get_move()
                if move:
                    moves.append(move)
        if moves:
            Move.save(moves)
            # Skip MoveFutureWarning as it is newly created moves
            with Transaction().set_user(0):
                Move.do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, inventories):
        Line = Pool().get("stock.inventory.line")
        Line.cancel_move([l for i in inventories for l in i.lines])

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        config = Configuration(1)
        vlist = [x.copy() for x in vlist]
        default_company = cls.default_company()
        for values in vlist:
            if values.get('number') is None:
                values['number'] = config.get_multivalue(
                    'inventory_sequence',
                    company=values.get('company', default_company)).get()
        inventories = super(Inventory, cls).create(vlist)
        cls.complete_lines(inventories, fill=False)
        return inventories

    @classmethod
    def write(cls, *args):
        super().write(*args)
        inventories = cls.browse(set(sum(args[::2], [])))
        cls.complete_lines(inventories, fill=False)

    @classmethod
    def copy(cls, inventories, default=None):
        pool = Pool()
        Date = pool.get('ir.date')

        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('date', Date.today())
        default.setdefault('lines.moves', None)
        default.setdefault('number', None)

        new_inventories = super().copy(inventories, default=default)
        cls.complete_lines(new_inventories, fill=False)
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
            with Transaction().set_context(stock_date_end=inventory.date):
                if fill:
                    pbl = Product.products_by_location(
                        [inventory.location.id],
                        grouping=grouping)
                else:
                    product_ids = [l.product.id for l in inventory.lines]
                    pbl = defaultdict(int)
                    for product_ids in grouped_slice(product_ids):
                        pbl.update(Product.products_by_location(
                                [inventory.location.id],
                                grouping=grouping,
                                grouping_filter=(list(product_ids),)))

            # Index some data
            product2type = {}
            product2consumable = {}
            for product in Product.browse({line[1] for line in pbl}):
                product2type[product.id] = product.type
                product2consumable[product.id] = product.consumable

            # Update existing lines
            for line in inventory.lines:
                if line.product.type != 'goods':
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
            for key, quantity in pbl.items():
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

    @classmethod
    @ModelView.button_action('stock.wizard_inventory_count')
    def count(cls, inventories):
        cls.complete_lines(inventories)


class InventoryLine(ModelSQL, ModelView):
    'Stock Inventory Line'
    __name__ = 'stock.inventory.line'
    _states = {
        'readonly': Eval('inventory_state') != 'draft',
        }

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ], states=_states)
    uom = fields.Function(fields.Many2One('product.uom', 'UOM',
        help="The unit in which the quantity is specified."), 'get_uom')
    expected_quantity = fields.Float(
        "Expected Quantity", digits='uom', required=True, readonly=True,
        states={
            'invisible': Eval('id', -1) < 0,
        },
        help="The quantity the system calculated should be in the location.")
    quantity = fields.Float(
        "Actual Quantity", digits='uom', states=_states,
        help="The actual quantity found in the location.")
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Inventory', required=True,
        ondelete='CASCADE',
        states={
            'readonly': _states['readonly'] & Bool(Eval('inventory')),
            },
        help="The inventory the line belongs to.")
    inventory_location = fields.Function(
        fields.Many2One('stock.location', "Location"),
        'on_change_with_inventory_location',
        searcher='search_inventory_location')
    inventory_date = fields.Function(
        fields.Date("Date"),
        'on_change_with_inventory_date',
        searcher='search_inventory_date')
    inventory_state = fields.Function(
        fields.Selection('get_inventory_states', "Inventory State",
        depends={'inventory'}),
        'on_change_with_inventory_state')

    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        cls.__access__.add('inventory')
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_line_qty_pos', Check(t, t.quantity >= 0),
                'stock.msg_inventory_line_quantity_positive'),
            ]
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()
        pool = Pool()
        Move = pool.get('stock.move')
        sql_table = cls.__table__()
        move_table = Move.__table__()

        super(InventoryLine, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 3.0: use Move origin
        if table.column_exist('move'):
            cursor.execute(*sql_table.select(sql_table.id, sql_table.move,
                    where=sql_table.move != Null))
            for line_id, move_id in cursor:
                update.execute(*move_table.update(
                        columns=[move_table.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=move_table.id == move_id))
            table.drop_column('move')

        # Migration from 4.6: drop required on quantity
        table.not_null_action('quantity', action='remove')

    @staticmethod
    def default_expected_quantity():
        return 0.

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.uom = self.product.default_uom

    @fields.depends('inventory', '_parent_inventory.location')
    def on_change_with_inventory_location(self, name=None):
        if self.inventory and self.inventory.location:
            return self.inventory.location.id

    @classmethod
    def search_inventory_location(cls, name, clause):
        nested = clause[0].lstrip(name)
        return [('inventory.' + name + nested,) + tuple(clause[1:])]

    @fields.depends('inventory', '_parent_inventory.date')
    def on_change_with_inventory_date(self, name=None):
        if self.inventory:
            return self.inventory.date

    @classmethod
    def search_inventory_date(cls, name, clause):
        return [('inventory.date',) + tuple(clause[1:])]

    @classmethod
    def get_inventory_states(cls):
        pool = Pool()
        Inventory = pool.get('stock.inventory')
        return Inventory.fields_get(['state'])['state']['selection']

    @fields.depends('inventory', '_parent_inventory.state')
    def on_change_with_inventory_state(self, name=None):
        if self.inventory:
            return self.inventory.state
        return 'draft'

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

    def get_uom(self, name):
        return self.product.default_uom.id

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

        qty = self.quantity
        if qty is None:
            if self.inventory.empty_quantity is None:
                raise InventoryValidationError(
                    gettext('stock.msg_inventory_missing_empty_quantity',
                        inventory=self.inventory.rec_name))
            if self.inventory.empty_quantity == 'keep':
                return
            else:
                qty = 0.0

        delta_qty = Uom.compute_qty(self.uom,
            self.expected_quantity - qty,
            self.uom)
        if delta_qty == 0.0:
            return
        from_location = self.inventory.location
        to_location = self.inventory.location.lost_found_used
        if not to_location:
            raise InventoryValidationError(
                gettext('stock.msg_inventory_location_missing_lost_found',
                    inventory=self.inventory.rec_name,
                    location=self.inventory.location.rec_name))
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
        if self.expected_quantity == quantity:
            return values
        values['expected_quantity'] = quantity
        return values

    @classmethod
    def create_values4complete(cls, inventory, quantity):
        '''
        Return create values to complete inventory
        '''
        return {
            'inventory': inventory.id,
            'expected_quantity': quantity,
        }

    @classmethod
    def delete(cls, lines):
        for line in lines:
            if line.inventory_state not in {'cancelled', 'draft'}:
                raise AccessError(
                    gettext('stock.msg_inventory_line_delete_cancel',
                        line=line.rec_name,
                        inventory=line.inventory.rec_name))
        super(InventoryLine, cls).delete(lines)


class Count(Wizard):
    "Stock Inventory Count"
    __name__ = 'stock.inventory.count'
    start_state = 'search'

    search = StateView(
        'stock.inventory.count.search',
        'stock.inventory_count_search_view_form', [
            Button("End", 'end', 'tryton-cancel'),
            Button("Select", 'quantity', 'tryton-forward', default=True),
            ])
    quantity = StateView(
        'stock.inventory.count.quantity',
        'stock.inventory_count_quantity_view_form', [
            Button("Cancel", 'search', 'tryton-cancel'),
            Button("Add", 'add', 'tryton-ok', default=True),
            ])
    add = StateTransition()

    def default_quantity(self, fields):
        pool = Pool()
        InventoryLine = pool.get('stock.inventory.line')
        Warning = pool.get('res.user.warning')
        values = {}
        lines = InventoryLine.search(
            self.get_line_domain(self.record), limit=1)
        if not lines:
            warning_name = '%s.%s.count_create' % (
                self.record, self.search.search)
            if Warning.check(warning_name):
                raise InventoryCountWarning(warning_name,
                    gettext('stock.msg_inventory_count_create_line',
                        search=self.search.search.rec_name))
            line, = InventoryLine.create([self.get_line_values(self.record)])
        else:
            line, = lines
        values['line'] = line.id
        values['product'] = line.product.id
        values['uom'] = line.uom.id
        if line.uom.rounding == 1:
            values['quantity'] = 1.
        return values

    def get_line_domain(self, inventory):
        pool = Pool()
        Product = pool.get('product.product')
        domain = [
            ('inventory', '=', inventory.id),
            ]
        if isinstance(self.search.search, Product):
            domain.append(('product', '=', self.search.search.id))
        return domain

    def get_line_values(self, inventory):
        pool = Pool()
        Product = pool.get('product.product')
        InventoryLine = pool.get('stock.inventory.line')
        values = InventoryLine.create_values4complete(inventory, 0)
        if isinstance(self.search.search, Product):
            values['product'] = self.search.search.id
        return values

    def transition_add(self):
        if self.quantity.line and self.quantity.quantity:
            line = self.quantity.line
            if line.quantity:
                line.quantity += self.quantity.quantity
            else:
                line.quantity = self.quantity.quantity
            line.save()
        return 'search'


class CountSearch(ModelView):
    "Stock Inventory Count"
    __name__ = 'stock.inventory.count.search'

    search = fields.Reference(
        "Search", [
            ('product.product', "Product"),
            ],
        required=True,
        domain={
            'product.product': [
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ],
            },
        help="The item that's counted.")

    @classmethod
    def default_search(cls):
        return 'product.product,-1'


class CountQuantity(ModelView):
    "Stock Inventory Count"
    __name__ = 'stock.inventory.count.quantity'

    line = fields.Many2One(
        'stock.inventory.line', "Line", readonly=True, required=True)
    product = fields.Many2One('product.product', "Product", readonly=True)
    uom = fields.Many2One('product.uom', "UOM", readonly=True,
        help="The unit in which the quantities are specified.")
    total_quantity = fields.Float(
        "Total Quantity", digits='uom', readonly=True,
        help="The total amount of the line counted so far.")

    quantity = fields.Float(
        "Quantity", digits='uom', required=True,
        help="The quantity to add to the existing count.")

    @fields.depends('quantity', 'line')
    def on_change_quantity(self):
        if self.line:
            self.total_quantity = (
                (self.line.quantity or 0) + (self.quantity or 0))
