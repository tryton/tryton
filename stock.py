# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from copy import copy
from functools import wraps

from sql import Column

from trytond.i18n import gettext
from trytond.model import Model, ModelSQL, ModelView, fields
from trytond.model.exceptions import (
    AccessError, RequiredValidationError, ValidationError)
from trytond.modules.stock import StockMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Len
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


def check_no_move(func):
    def find_moves(cls, records, state=None):
        pool = Pool()
        Move = pool.get('stock.move')
        for sub_records in grouped_slice(records):
            domain = [
                ('lot', 'in', [r.id for r in sub_records])
                ]
            if state:
                domain.append(('state', '=', state))
            moves = Move.search(domain, limit=1, order=[])
            if moves:
                return True
        return False

    @wraps(func)
    def decorator(cls, *args):
        transaction = Transaction()
        if (transaction.user != 0
                and transaction.context.get('_check_access')):
            actions = iter(args)
            for records, values in zip(actions, actions):
                for field, state, error in cls._modify_no_move:
                    if field in values:
                        if find_moves(cls, records, state):
                            raise AccessError(gettext(error))
                        # No moves for those records
                        break
        func(cls, *args)
    return decorator


class LotMixin:
    __slots__ = ()
    number = fields.Char(
        "Number", required=True, select=True,
        states={
            'required': ~Eval('has_sequence') | (Eval('id', -1) >= 0),
            })
    product = fields.Many2One('product.product', 'Product', required=True)
    has_sequence = fields.Function(
        fields.Boolean("Has Sequence"), 'on_change_with_has_sequence')

    @fields.depends('product')
    def on_change_with_has_sequence(self, name=None):
        if self.product:
            return bool(self.product.lot_sequence)


class Lot(ModelSQL, ModelView, LotMixin, StockMixin):
    "Stock Lot"
    __name__ = 'stock.lot'
    _rec_name = 'number'

    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
        searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
        'get_quantity', searcher='search_quantity')
    default_uom = fields.Function(
        fields.Many2One('product.uom', "Default UOM"),
        'on_change_with_default_uom')
    default_uom_digits = fields.Function(fields.Integer("Default Unit Digits"),
        'on_change_with_default_uom_digits')

    @classmethod
    def __setup__(cls):
        super(Lot, cls).__setup__()
        cls._modify_no_move = [
            ('product', None, 'stock_lot.msg_change_product'),
            ]
        cls._buttons.update({
                'upward_traces': {},
                'downward_traces': {},
                })

    @classmethod
    def get_quantity(cls, lots, name):
        location_ids = Transaction().context.get('locations')
        product_ids = list(set(l.product.id for l in lots))
        quantities = {}
        for product_ids in grouped_slice(product_ids):
            quantities.update(cls._get_quantity(lots, name, location_ids,
                    grouping=('product', 'lot',),
                    grouping_filter=(list(product_ids),)))
        return quantities

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain,
            grouping=('product', 'lot'))

    @fields.depends('product')
    def on_change_with_default_uom(self, name=None):
        if self.product:
            return self.product.default_uom.id

    @fields.depends('product')
    def on_change_with_default_uom_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('number'):
                values['number'] = cls._new_number(values)
        return super().create(vlist)

    @classmethod
    def _new_number(cls, values):
        pool = Pool()
        Product = pool.get('product.product')
        if values.get('product'):
            product = Product(values['product'])
            if product.lot_sequence:
                return product.lot_sequence.get()

    @classmethod
    @check_no_move
    def write(cls, *args):
        super(Lot, cls).write(*args)

    @classmethod
    @ModelView.button_action('stock_lot.act_lot_trace_upward_relate')
    def upward_traces(cls, lots):
        pass

    @classmethod
    @ModelView.button_action('stock_lot.act_lot_trace_downward_relate')
    def downward_traces(cls, lots):
        pass


class LotTrace(ModelSQL, ModelView):
    "Lot Trace"
    __name__ = 'stock.lot.trace'

    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    lot = fields.Many2One('stock.lot', "Lot")

    quantity = fields.Float("Quantity", digits='unit')
    unit = fields.Many2One('product.uom', "Unit")

    company = fields.Many2One('company.company', "Company")
    date = fields.Date("Date")
    shipment = fields.Reference("Shipment", 'get_shipments')
    document = fields.Function(
        fields.Reference("Document", 'get_documents'), 'get_document')

    upward_traces = fields.Function(
        fields.Many2Many(
            'stock.lot.trace', None, None, "Upward Traces"),
        'get_upward_traces')
    downward_traces = fields.Function(
        fields.Many2Many(
            'stock.lot.trace', None, None, "Downward Traces"),
        'get_downward_traces')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        move = Move.__table__()
        return (
            move.select(
                *cls._columns(move),
                where=move.state == 'done'))

    @classmethod
    def _columns(cls, move):
        return [
            move.id.as_('id'),
            move.create_uid.as_('create_uid'),
            move.create_date.as_('create_date'),
            move.write_uid.as_('write_uid'),
            move.write_date.as_('write_date'),
            move.product.as_('product'),
            move.lot.as_('lot'),
            move.quantity.as_('quantity'),
            move.uom.as_('unit'),
            move.company.as_('company'),
            move.effective_date.as_('date'),
            move.shipment.as_('shipment'),
            ]

    def get_rec_name(self, name):
        return self.document.rec_name if self.document else str(self.id)

    @classmethod
    def get_shipments(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_shipment()

    @classmethod
    def get_documents(cls):
        return cls.get_shipments()

    def get_document(self, name):
        if self.shipment:
            return str(self.shipment)

    @classmethod
    def _is_trace_move(cls, move):
        return move.state == 'done'

    @classmethod
    def _trace_move_order_key(cls, move):
        return (move.effective_date,)

    def get_upward_traces(self, name):
        return list(map(int, sorted(filter(
                        self._is_trace_move, self._get_upward_traces()),
                    key=self._trace_move_order_key)))

    def _get_upward_traces(self):
        return set()

    def get_downward_traces(self, name):
        return list(map(int, sorted(filter(
                        self._is_trace_move, self._get_downward_traces()),
                    key=self._trace_move_order_key)))

    def _get_downward_traces(self):
        return set()


class LotByLocationContext(ModelView):
    'Lot by Location'
    __name__ = 'stock.lots_by_location.context'
    forecast_date = fields.Date(
        'At Date', help=('Allow to compute expected '
            'stock quantities for this date.\n'
            '* An empty value is an infinite date in the future.\n'
            '* A date in the past will provide historical values.'))
    stock_date_end = fields.Function(fields.Date('At Date'),
        'on_change_with_stock_date_end')

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class LotsByLocations(ModelSQL, ModelView):
    "Lots by Locations"
    __name__ = 'stock.lots_by_locations'

    lot = fields.Many2One('stock.lot', "Lot")
    product = fields.Many2One('product.product', "Product")
    quantity = fields.Function(
        fields.Float(
            "Quantity", digits=(16, Eval('default_uom_digits', 2))),
        'get_lot', searcher='search_lot')
    forecast_quantity = fields.Function(
        fields.Float(
            "Forecast Quantity", digits=(16, Eval('default_uom_digits', 2))),
        'get_lot', searcher='search_lot')
    default_uom = fields.Function(
        fields.Many2One('product.uom', "Default UOM"),
        'get_lot', searcher='search_lot')
    default_uom_digits = fields.Function(
        fields.Integer("Default UOM Digits"), 'get_lot')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('lot', 'ASC'))
        cls._order.insert(1, ('product', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Lot = pool.get('stock.lot')
        lot = Lot.__table__()
        columns = []
        for fname, field in cls._fields.items():
            if not hasattr(field, 'set'):
                if (isinstance(field, fields.Many2One)
                        and field.get_target() == Lot):
                    column = Column(lot, 'id')
                else:
                    column = Column(lot, fname)
                columns.append(column.as_(fname))
        return lot.select(*columns)

    def get_rec_name(self, name):
        return self.lot.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('lot.rec_name',) + tuple(clause[1:])]

    def get_lot(self, name):
        value = getattr(self.lot, name)
        if isinstance(value, Model):
            value = value.id
        return value

    @classmethod
    def search_lot(cls, name, clause):
        nested = clause[0].lstrip(name)
        return [('lot.' + name + nested,) + tuple(clause[1:])]


class LotByWarehouseContext(LotByLocationContext):
    "Lot by Warehouse"
    __name__ = 'stock.lots_by_warehouse.context'
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        )
    locations = fields.Function(
        fields.Many2Many('stock.location', None, None, "Locations"),
        'on_change_with_locations')

    @classmethod
    def default_warehouse(cls):
        return Pool().get('stock.location').get_default_warehouse()

    @fields.depends('warehouse')
    def on_change_with_locations(self, name=None):
        locations = []
        if self.warehouse:
            locations.append(self.warehouse.id)
        return locations


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    @classmethod
    def _get_quantity_grouping(cls):
        pool = Pool()
        Lot = pool.get('stock.lot')
        context = Transaction().context
        grouping, grouping_filter, key = super()._get_quantity_grouping()
        if context.get('lot') is not None:
            try:
                lot, = Lot.search([('id', '=', context['lot'])])
            except ValueError:
                pass
            else:
                grouping = ('product', 'lot',)
                grouping_filter = ([lot.product.id], [lot.id])
                key = (lot.product.id, lot.id)
        return grouping, grouping_filter, key


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('state').in_(['cancelled', 'done']),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'add_lots_wizard': {
                    'invisible': ~Eval('state').in_(['draft', 'assigned']),
                    'readonly': Bool(Eval('lot')),
                    'depends': ['lot', 'state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_lot.wizard_move_add_lots')
    def add_lots_wizard(cls, moves):
        pass

    def check_lot(self):
        "Check if lot is required"
        if (self.state == 'done'
                and self.internal_quantity
                and not self.lot
                and self.product.lot_is_required(
                    self.from_location, self.to_location)):
            raise RequiredValidationError(
                gettext('stock_lot.msg_lot_required',
                    product=self.product.rec_name))

    @classmethod
    def validate(cls, moves):
        super(Move, cls).validate(moves)
        for move in moves:
            move.check_lot()

    @classmethod
    def assign_try(cls, moves, with_childs=True, grouping=('product',)):
        if 'lot' not in grouping:
            moves_with_lot, moves_without_lot = [], []
            for move in moves:
                if move.lot:
                    moves_with_lot.append(move)
                else:
                    moves_without_lot.append(move)
            success = super().assign_try(
                moves_with_lot, with_childs, grouping=grouping + ('lot',))
            success &= super().assign_try(
                moves_without_lot, with_childs, grouping=grouping)
        else:
            success = super().assign_try(moves, with_childs, grouping)
        return success


class MoveAddLots(Wizard):
    "Add Lots"
    __name__ = 'stock.move.add.lots'
    start = StateView('stock.move.add.lots.start',
        'stock_lot.move_add_lots_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Add", 'add', 'tryton-ok', default=True),
            ])
    add = StateTransition()

    def default_start(self, fields):
        default = {}
        if 'product' in fields:
            default['product'] = self.record.product.id
        if 'quantity' in fields:
            default['quantity'] = self.record.quantity
        if 'unit' in fields:
            default['unit'] = self.record.uom.id
        return default

    def transition_add(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Lot = pool.get('stock.lot')
        lang = Lang.get()
        quantity_remaining = self.start.on_change_with_quantity_remaining()
        if quantity_remaining < 0:
            digits = self.record.uom.digits
            move_quantity = self.record.quantity
            lot_quantity = self.record.quantity - quantity_remaining
            raise ValidationError(gettext(
                    'stock_lot.msg_move_add_lot_quantity',
                    lot_quantity=lang.format_number(lot_quantity, digits),
                    move_quantity=lang.format_number(move_quantity, digits)))
        lots = []
        for line in self.start.lots:
            lot = line.get_lot(self.record)
            lots.append(lot)
        Lot.save(lots)
        if quantity_remaining:
            self.record.quantity = quantity_remaining
            self.record.save()
        for i, (line, lot) in enumerate(zip(self.start.lots, lots)):
            if not i and not quantity_remaining:
                self.record.quantity = line.quantity
                self.record.lot = lot
                self.record.save()
            else:
                with Transaction().set_context(_stock_move_split=True):
                    self.model.copy([self.record], {
                            'quantity': line.quantity,
                            'lot': lot.id,
                            })
        return 'end'


class MoveAddLotsStart(ModelView):
    "Add Lots"
    __name__ = 'stock.move.add.lots.start'

    product = fields.Many2One('product.product', "Product", readonly=True)
    quantity = fields.Float("Quantity", digits='unit', readonly=True)
    unit = fields.Many2One('product.uom', "Unit", readonly=True)
    quantity_remaining = fields.Function(
        fields.Float("Quantity Remaining", digits='unit'),
        'on_change_with_quantity_remaining')

    lots = fields.One2Many(
        'stock.move.add.lots.start.lot', 'parent', "Lots",
        domain=[
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'readonly': ~Eval('quantity_remaining', 0),
            })

    duplicate_lot_number = fields.Integer(
        "Duplicate Lot Number",
        states={
            'invisible': Len(Eval('lots')) != 1,
            },
        help="The number of times the lot must be duplicated.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            duplicate_lot={
                'invisible': Len(Eval('lots')) != 1,
                'readonly': (~Eval('duplicate_lot_number')
                    | (Eval('duplicate_lot_number', 0) <= 0)),
                'depends': ['lots', 'duplicate_lot_number'],
                },
            )

    @fields.depends('quantity', 'lots', 'unit')
    def on_change_with_quantity_remaining(self, name=None):
        if self.quantity is not None:
            quantity = self.quantity
            if self.lots:
                for lot in self.lots:
                    quantity -= getattr(lot, 'quantity', 0) or 0
            if self.unit:
                quantity = self.unit.round(quantity)
            return quantity

    @ModelView.button_change(
        'lots', 'duplicate_lot_number',
        methods=['on_change_with_quantity_remaining'])
    def duplicate_lot(self):
        lots = list(self.lots)
        template, = self.lots
        for i in range(self.duplicate_lot_number):
            lot = copy(template)
            lot._id = None
            lots.append(lot)
        self.lots = lots
        self.quantity_remaining = self.on_change_with_quantity_remaining()


class MoveAddLotsStartLot(ModelView, LotMixin):
    "Add Lots"
    __name__ = 'stock.move.add.lots.start.lot'

    parent = fields.Many2One('stock.move.add.lots.start', "Parent")
    quantity = fields.Float("Quantity", digits='unit', required=True)
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')

    @fields.depends(
        'parent', '_parent_parent.quantity_remaining')
    def on_change_parent(self):
        if (self.parent
                and self.parent.quantity_remaining is not None):
            self.quantity = self.parent.quantity_remaining

    @fields.depends('parent', '_parent_parent.unit')
    def on_change_with_unit(self, name=None):
        if self.parent and self.parent.unit:
            return self.parent.unit.id

    @fields.depends('number', 'product', methods=['_set_lot_values'])
    def on_change_number(self):
        pool = Pool()
        Lot = pool.get('stock.lot')
        if self.number and self.product:
            lots = Lot.search([
                    ('number', '=', self.number),
                    ('product', '=', self.product.id),
                    ])
            if len(lots) == 1:
                lot, = lots
                self._set_lot_values(lot)

    def _set_lot_values(self, lot):
        pass

    def get_lot(self, move):
        pool = Pool()
        Lot = pool.get('stock.lot')
        values = self._get_lot_values(move)
        lots = Lot.search(
            [(k, '=', v) for k, v in values.items()],
            limit=1)
        if lots:
            lot, = lots
        else:
            lot = Lot()
            for k, v in values.items():
                setattr(lot, k, v)
        return lot

    def _get_lot_values(self, move):
        return {
            'number': self.number,
            'product': move.product,
            }


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, outgoing_move):
        move = super()._get_inventory_move(outgoing_move)
        if move and outgoing_move.lot:
            move.lot = outgoing_move.lot
        return move

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    def _sync_move_key(self, move):
        return super()._sync_move_key(move) + (('lot', move.lot),)


class Period(metaclass=PoolMeta):
    __name__ = 'stock.period'
    lot_caches = fields.One2Many('stock.period.cache.lot', 'period',
        'Lot Caches', readonly=True)

    @classmethod
    def groupings(cls):
        return super(Period, cls).groupings() + [('product', 'lot')]

    @classmethod
    def get_cache(cls, grouping):
        pool = Pool()
        Cache = super(Period, cls).get_cache(grouping)
        if grouping == ('product', 'lot'):
            return pool.get('stock.period.cache.lot')
        return Cache


class PeriodCacheLot(ModelSQL, ModelView):
    '''
    Stock Period Cache per Lot

    It is used to store cached computation of stock quantities per lot.
    '''
    __name__ = 'stock.period.cache.lot'
    period = fields.Many2One('stock.period', 'Period', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    location = fields.Many2One('stock.location', 'Location', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True, ondelete='CASCADE')
    lot = fields.Many2One('stock.lot', 'Lot', readonly=True,
        ondelete='CASCADE')
    internal_quantity = fields.Float('Internal Quantity', readonly=True)


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def grouping(cls):
        return super(Inventory, cls).grouping() + ('lot', )


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('inventory_state') != 'draft',
            })

    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        cls._order.insert(1, ('lot', 'ASC'))

    def get_rec_name(self, name):
        rec_name = super(InventoryLine, self).get_rec_name(name)
        if self.lot:
            rec_name += ' - %s' % self.lot.rec_name
        return rec_name

    def get_move(self):
        move = super(InventoryLine, self).get_move()
        if move:
            move.lot = self.lot
        return move


class InventoryCount(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count'

    def default_quantity(self, fields):
        pool = Pool()
        Product = pool.get('product.product')
        inventory = self.record
        if isinstance(self.search.search, Product):
            product = self.search.search
            if product.lot_is_required(
                    inventory.location, inventory.location.lost_found_used):
                raise RequiredValidationError(
                    gettext('stock_lot.msg_only_lot',
                        product=product.rec_name))
        return super(InventoryCount, self).default_quantity(fields)

    def get_line_domain(self, inventory):
        pool = Pool()
        Lot = pool.get('stock.lot')
        domain = super(InventoryCount, self).get_line_domain(inventory)
        if isinstance(self.search.search, Lot):
            domain.append(('lot', '=', self.search.search.id))
        return domain

    def get_line_values(self, inventory):
        pool = Pool()
        Lot = pool.get('stock.lot')
        values = super(InventoryCount, self).get_line_values(inventory)
        if isinstance(self.search.search, Lot):
            lot = self.search.search
            values['product'] = lot.product.id
            values['lot'] = lot.id
        return values


class InventoryCountSearch(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count.search'

    @classmethod
    def __setup__(cls):
        super(InventoryCountSearch, cls).__setup__()
        cls.search.selection.append(('stock.lot', "Lot"))
